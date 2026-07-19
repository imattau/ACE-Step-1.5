//! Collect system-level diagnostics for the desktop startup screen.
//!
//! Gathers kernel, Flatpak, and XDG path info using only stdlib so that
//! no new crate dependencies are introduced.

use std::process::Command;

use serde::Serialize;

use crate::backend::BackendManager;
use crate::paths::RuntimePaths;

/// Combined system-level diagnostics report.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemReport {
    // Kernel / arch
    pub kernel_name: String,
    pub kernel_release: String,
    pub arch: String,
    // Flatpak
    pub flatpak_id: Option<String>,
    pub runtime_branch: Option<String>,
    // Paths
    pub checkpoints_dir: String,
    pub logs_dir: String,
    pub outputs_dir: String,
    pub model_manifest: String,
    pub runtime_metadata: String,
    // Application
    pub app_version: String,
    // Backend
    pub backend_phase: String,
    pub backend_message: String,
    pub backend_url: Option<String>,
    pub backend_pid: Option<u32>,
    // Writable paths exist
    pub checkpoints_exists: bool,
    pub logs_exists: bool,
    pub outputs_exists: bool,
}

/// Gather a complete system-level report.
pub fn gather(paths: &RuntimePaths, backend: &BackendManager) -> SystemReport {
    let status = backend.status();
    let metadata = backend.metadata();
    SystemReport {
        kernel_name: uname_field("-s").unwrap_or_else(|| "unknown".into()),
        kernel_release: uname_field("-r").unwrap_or_else(|| "unknown".into()),
        arch: std::env::consts::ARCH.to_string(),
        flatpak_id: std::env::var("FLATPAK_ID").ok(),
        runtime_branch: flatpak_runtime_branch(),
        checkpoints_dir: paths.checkpoints.to_string_lossy().into(),
        logs_dir: paths.logs.to_string_lossy().into(),
        outputs_dir: paths.outputs.to_string_lossy().into(),
        model_manifest: paths.model_manifest.to_string_lossy().into(),
        runtime_metadata: paths.runtime_metadata.to_string_lossy().into(),
        app_version: env!("CARGO_PKG_VERSION").to_string(),
        backend_phase: status.phase,
        backend_message: status.message,
        backend_url: status.url,
        backend_pid: metadata.map(|m| m.pid),
        checkpoints_exists: paths.checkpoints.exists(),
        logs_exists: paths.logs.exists(),
        outputs_exists: paths.outputs.exists(),
    }
}

/// Format a SystemReport as a human-readable multi-line string.
pub fn format_report(system: &SystemReport, python_info: Option<&str>) -> String {
    let mut lines: Vec<String> = Vec::new();
    lines.push("── ACE-Step Diagnostics ──".into());
    lines.push(format!("App version:          {}", system.app_version));
    lines.push(format!("Kernel:               {} {}", system.kernel_name, system.kernel_release));
    lines.push(format!("Architecture:         {}", system.arch));
    lines.push(format!("Flatpak ID:           {}", system.flatpak_id.as_deref().unwrap_or("(none)")));
    lines.push(format!("Runtime branch:       {}", system.runtime_branch.as_deref().unwrap_or("(none)")));
    lines.push(String::new());
    lines.push("── Paths ──".into());
    lines.push(format!("Checkpoints:          {}", system.checkpoints_dir));
    lines.push(format!("Logs:                 {}", system.logs_dir));
    lines.push(format!("Outputs:              {}", system.outputs_dir));
    lines.push(String::new());
    lines.push("── Backend ──".into());
    lines.push(format!("Phase:                {}", system.backend_phase));
    lines.push(format!("Message:              {}", system.backend_message));
    if let Some(pid) = system.backend_pid {
        lines.push(format!("PID:                  {pid}"));
    }
    if let Some(ref url) = system.backend_url {
        lines.push(format!("URL:                  {url}"));
    }
    if let Some(info) = python_info {
        lines.push(String::new());
        lines.push("── Python ──".into());
        for line in info.lines() {
            lines.push(format!("  {line}"));
        }
    }
    lines.join("\n")
}

fn uname_field(flag: &str) -> Option<String> {
    Command::new("uname")
        .arg(flag)
        .output()
        .ok()
        .and_then(|output| {
            if output.status.success() {
                String::from_utf8(output.stdout).ok().map(|s| s.trim().to_string())
            } else {
                None
            }
        })
}

fn flatpak_runtime_branch() -> Option<String> {
    let info_path = std::path::Path::new("/run/host/monitor/info");
    if info_path.exists() {
        if let Ok(content) = std::fs::read_to_string(info_path) {
            for line in content.lines() {
                if line.starts_with("org.gnome.Platform") {
                    let parts: Vec<&str> = line.splitn(3, '/').collect();
                    if parts.len() >= 2 {
                        return Some(parts[1].to_string());
                    }
                }
            }
        }
    }
    std::env::var("FLATPAK_RUNTIME_BRANCH").ok()
}
