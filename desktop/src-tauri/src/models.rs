//! Inspect and prepare the private desktop model installation.

use std::{path::PathBuf, process::Command};

use serde::{Deserialize, Serialize};

use crate::backend::backend_command;

pub const DEFAULT_LM: &str = "acestep-5Hz-lm-1.7B";

pub fn load_selection(path: &PathBuf) -> String {
    std::fs::read_to_string(path)
        .ok()
        .and_then(|value| serde_json::from_str::<serde_json::Value>(&value).ok())
        .and_then(|value| value["lmModel"].as_str().map(str::to_owned))
        .unwrap_or_else(|| DEFAULT_LM.into())
}

pub fn save_selection(path: &PathBuf, lm_model: &str) -> Result<(), String> {
    let value = serde_json::json!({"desktopSchema": 1, "lmModel": lm_model});
    std::fs::write(path, value.to_string())
        .map_err(|error| format!("model selection could not be saved: {error}"))
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelStatus {
    pub ready: bool,
    #[serde(alias = "lm_model")]
    pub lm_model: String,
    pub installed: Vec<String>,
    pub missing: Vec<String>,
    #[serde(alias = "required_bytes")]
    pub required_bytes: u64,
    #[serde(alias = "free_bytes")]
    pub free_bytes: u64,
    #[serde(alias = "checkpoints_dir")]
    pub checkpoints_dir: String,
}

pub fn inspect(checkpoints: &PathBuf, lm_model: &str) -> Result<ModelStatus, String> {
    run_action("status", checkpoints, lm_model)
}

pub fn install(checkpoints: &PathBuf, lm_model: &str) -> Result<ModelStatus, String> {
    run_action("install", checkpoints, lm_model)
}

fn run_action(action: &str, checkpoints: &PathBuf, lm_model: &str) -> Result<ModelStatus, String> {
    let output = Command::new(backend_command())
        .args([
            "--model-action",
            action,
            "--checkpoints-dir",
            &checkpoints.to_string_lossy(),
            "--lm-model",
            lm_model,
        ])
        .output()
        .map_err(|error| format!("model {action} failed to start: {error}"))?;
    if !output.status.success() {
        let error = String::from_utf8_lossy(&output.stderr);
        return Err(format!("model {action} failed: {}", error.trim()));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let result = stdout
        .lines()
        .last()
        .ok_or("model action returned no status")?;
    serde_json::from_str(result).map_err(|error| format!("invalid model status: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn model_status_deserializes_desktop_protocol() {
        let status: ModelStatus = serde_json::from_str(
            r#"{"ready":false,"lm_model":"acestep-5Hz-lm-1.7B","installed":[],
            "missing":["vae"],"required_bytes":100,"free_bytes":200,
            "checkpoints_dir":"/tmp/models"}"#,
        )
        .expect("model status");
        assert!(!status.ready);
        assert_eq!(status.missing, vec!["vae"]);
    }
}
