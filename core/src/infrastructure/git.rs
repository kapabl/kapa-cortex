use crate::domain::entities::ChangedFile;
use std::process::Command;

pub fn current_branch() -> Result<String, String> {
    run_git(&["rev-parse", "--abbrev-ref", "HEAD"])
}

pub fn detect_base() -> Result<String, String> {
    // Try common base branches
    for base in &["main", "master", "develop"] {
        if run_git(&["rev-parse", "--verify", base]).is_ok() {
            return Ok(base.to_string());
        }
    }
    Err("Could not detect base branch".to_string())
}

pub fn diff_stat(base: &str) -> Result<Vec<ChangedFile>, String> {
    let output = run_git(&["diff", "--numstat", "--diff-filter=ACDMR", base])?;
    let mut files = Vec::new();
    for line in output.lines() {
        let parts: Vec<&str> = line.split('\t').collect();
        if parts.len() < 3 {
            continue;
        }
        let added: i64 = parts[0].parse().unwrap_or(0);
        let removed: i64 = parts[1].parse().unwrap_or(0);
        let path = parts[2].to_string();
        files.push(ChangedFile {
            path,
            added,
            removed,
            status: "M".to_string(),
            diff_text: String::new(),
            complexity: 0,
            structural_ratio: 1.0,
        });
    }

    // Get actual status (A/M/D/R)
    let status_output = run_git(&["diff", "--name-status", "--diff-filter=ACDMR", base])?;
    for line in status_output.lines() {
        let parts: Vec<&str> = line.split('\t').collect();
        if parts.len() < 2 {
            continue;
        }
        let status = parts[0].chars().next().unwrap_or('M').to_string();
        let path = parts.last().unwrap_or(&"").to_string();
        if let Some(file) = files.iter_mut().find(|f| f.path == path) {
            file.status = status;
        }
    }

    Ok(files)
}

pub fn diff_text(base: &str, file_path: &str) -> Result<String, String> {
    run_git(&["diff", base, "--", file_path])
}

pub fn file_source(file_path: &str) -> Result<String, String> {
    run_git(&["show", &format!("HEAD:{}", file_path)])
}

pub fn cherry_pick_files(base: &str, branch_name: &str, files: &[String]) -> Result<(), String> {
    run_git(&["checkout", "-b", branch_name, base])?;
    let current = current_branch()?;
    for file in files {
        run_git(&["checkout", &current, "--", file])?;
    }
    run_git(&["add", "-A"])?;
    Ok(())
}

fn run_git(args: &[&str]) -> Result<String, String> {
    let output = Command::new("git")
        .args(args)
        .output()
        .map_err(|e| format!("git failed: {}", e))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("git {} failed: {}", args.join(" "), stderr.trim()));
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}
