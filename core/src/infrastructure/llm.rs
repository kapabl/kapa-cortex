use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
struct OllamaRequest {
    model: String,
    prompt: String,
    stream: bool,
}

#[derive(Debug, Deserialize)]
struct OllamaResponse {
    response: Option<String>,
}

pub struct LlmClient {
    base_url: String,
    model: String,
}

impl LlmClient {
    pub fn new(model: &str) -> Self {
        LlmClient {
            base_url: "http://localhost:11434".to_string(),
            model: model.to_string(),
        }
    }

    pub fn available(&self) -> bool {
        reqwest::blocking::get(&format!("{}/api/tags", self.base_url)).is_ok()
    }

    pub fn generate(&self, prompt: &str) -> Result<String, String> {
        let request = OllamaRequest {
            model: self.model.clone(),
            prompt: prompt.to_string(),
            stream: false,
        };

        let client = reqwest::blocking::Client::new();
        let response = client
            .post(&format!("{}/api/generate", self.base_url))
            .json(&request)
            .send()
            .map_err(|e| format!("LLM request failed: {}", e))?;

        let body: OllamaResponse = response
            .json()
            .map_err(|e| format!("LLM response parse failed: {}", e))?;

        body.response.ok_or_else(|| "Empty LLM response".to_string())
    }
}

/// Generate a PR description without LLM — rule-based fallback.
pub fn rule_based_description(files: &[String]) -> String {
    if files.is_empty() {
        return "Empty change set".to_string();
    }
    let file_list: Vec<&str> = files.iter().map(|f| f.as_str()).take(5).collect();
    format!(
        "Changes to {}{}",
        file_list.join(", "),
        if files.len() > 5 { format!(" and {} more", files.len() - 5) } else { String::new() }
    )
}
