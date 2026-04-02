use crate::domain::entities::AnalysisResult;

pub fn print_analysis_text(result: &AnalysisResult) {
    println!("\n  \x1b[1mBranch:\x1b[0m {} → {}", result.branch, result.base);
    println!("  \x1b[1mFiles:\x1b[0m {}", result.files.len());
    println!("  \x1b[1mProposed PRs:\x1b[0m {}\n", result.prs.len());

    for pr in &result.prs {
        let risk_color = match pr.risk_level.as_str() {
            "high" => "\x1b[31m",
            "medium" => "\x1b[33m",
            _ => "\x1b[32m",
        };
        println!(
            "  #{} {} {}{}\x1b[0m",
            pr.order, pr.title, risk_color, pr.risk_level
        );
        for file in &pr.files {
            println!("    {}", file);
        }
        if !pr.depends_on.is_empty() {
            let deps: Vec<String> = pr.depends_on.iter().map(|d| format!("#{}", d)).collect();
            println!("    \x1b[2mdepends on: {}\x1b[0m", deps.join(", "));
        }
        println!();
    }
}

pub fn print_analysis_json(result: &AnalysisResult) {
    println!("{}", serde_json::to_string_pretty(result).unwrap_or_default());
}
