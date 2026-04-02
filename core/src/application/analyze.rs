use crate::domain::entities::{AnalysisResult, ChangedFile, ProposedPr};
use crate::infrastructure::{git, llm};
use std::collections::HashMap;

/// Analyze a branch and propose stacked PRs.
pub fn analyze_branch(base: &str, max_files: usize, max_lines: i64) -> Result<AnalysisResult, String> {
    let branch = git::current_branch()?;
    let files = git::diff_stat(base)?;

    if files.is_empty() {
        return Ok(AnalysisResult {
            branch,
            base: base.to_string(),
            files: Vec::new(),
            prs: Vec::new(),
        });
    }

    let prs = group_into_prs(&files, max_files, max_lines);

    Ok(AnalysisResult {
        branch,
        base: base.to_string(),
        files,
        prs,
    })
}

fn group_into_prs(files: &[ChangedFile], max_files: usize, max_lines: i64) -> Vec<ProposedPr> {
    // Group by module (top-level directory)
    let mut groups: HashMap<String, Vec<&ChangedFile>> = HashMap::new();
    for file in files {
        let key = file.module_key();
        groups.entry(key).or_default().push(file);
    }

    let mut prs = Vec::new();
    let mut order: i64 = 1;

    // Text/docs files go first
    let doc_files: Vec<String> = files
        .iter()
        .filter(|f| f.is_text_or_docs())
        .map(|f| f.path.clone())
        .collect();
    if !doc_files.is_empty() {
        prs.push(ProposedPr {
            title: "Documentation updates".to_string(),
            description: llm::rule_based_description(&doc_files),
            files: doc_files,
            order,
            risk_level: "low".to_string(),
            depends_on: Vec::new(),
        });
        order += 1;
    }

    // Split remaining files by module, respecting max_files and max_lines
    for (module, module_files) in &groups {
        let code_files: Vec<&ChangedFile> = module_files
            .iter()
            .filter(|f| !f.is_text_or_docs())
            .cloned()
            .collect();
        if code_files.is_empty() {
            continue;
        }

        let mut current_files: Vec<String> = Vec::new();
        let mut current_lines: i64 = 0;

        for file in &code_files {
            if (current_files.len() >= max_files || current_lines + file.code_lines() > max_lines)
                && !current_files.is_empty()
            {
                prs.push(ProposedPr {
                    title: format!("{} changes (part {})", module, order),
                    description: llm::rule_based_description(&current_files),
                    files: current_files.clone(),
                    order,
                    risk_level: risk_level(&code_files),
                    depends_on: if order > 1 { vec![order - 1] } else { Vec::new() },
                });
                order += 1;
                current_files.clear();
                current_lines = 0;
            }
            current_files.push(file.path.clone());
            current_lines += file.code_lines();
        }

        if !current_files.is_empty() {
            prs.push(ProposedPr {
                title: format!("{} changes", module),
                description: llm::rule_based_description(&current_files),
                files: current_files,
                order,
                risk_level: risk_level(&code_files),
                depends_on: if order > 1 { vec![order - 1] } else { Vec::new() },
            });
            order += 1;
        }
    }

    prs
}

fn risk_level(files: &[&ChangedFile]) -> String {
    let total_lines: i64 = files.iter().map(|f| f.code_lines()).sum();
    let max_complexity: i64 = files.iter().map(|f| f.complexity).max().unwrap_or(0);

    if total_lines > 500 || max_complexity > 50 {
        "high".to_string()
    } else if total_lines > 200 || max_complexity > 20 {
        "medium".to_string()
    } else {
        "low".to_string()
    }
}
