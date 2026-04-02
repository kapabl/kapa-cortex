use serde::Serialize;
use std::path::Path;

const TEXT_EXTENSIONS: &[&str] = &[
    ".md", ".txt", ".rst", ".adoc", ".csv", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".lock", ".log",
];

#[derive(Debug, Clone, Serialize)]
pub struct ChangedFile {
    pub path: String,
    pub added: i64,
    pub removed: i64,
    pub status: String,
    pub diff_text: String,
    pub complexity: i64,
    pub structural_ratio: f64,
}

impl ChangedFile {
    pub fn is_text_or_docs(&self) -> bool {
        let ext = Path::new(&self.path)
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
            .unwrap_or_default();
        TEXT_EXTENSIONS.contains(&ext.as_str())
    }

    pub fn code_lines(&self) -> i64 {
        self.added + self.removed
    }

    pub fn module_key(&self) -> String {
        let parts: Vec<&str> = self.path.split('/').collect();
        if parts.len() <= 1 {
            "__root__".to_string()
        } else {
            parts[0].to_string()
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ImportRef {
    pub raw: String,
    pub module: String,
    pub kind: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SymbolDef {
    pub name: String,
    pub kind: String,
    pub line: i64,
    pub scope: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProposedPr {
    pub title: String,
    pub description: String,
    pub files: Vec<String>,
    pub order: i64,
    pub risk_level: String,
    pub depends_on: Vec<i64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AnalysisResult {
    pub branch: String,
    pub base: String,
    pub files: Vec<ChangedFile>,
    pub prs: Vec<ProposedPr>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExecutionStep {
    pub order: i64,
    pub command: String,
    pub description: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExecutionPlan {
    pub branch: String,
    pub base: String,
    pub steps: Vec<ExecutionStep>,
}
