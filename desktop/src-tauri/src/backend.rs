//! Own the fixed desktop backend process and authenticated readiness polling.

use std::{
    io::{BufRead, BufReader, Read},
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
};

use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::paths::RuntimePaths;
use crate::readiness::{poll_readiness, update_status};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendStatus {
    pub phase: String,
    pub message: String,
    pub url: Option<String>,
    pub recent_output: Vec<String>,
}

pub struct BackendManager {
    child: Mutex<Option<Child>>,
    metadata_path: PathBuf,
    status: Arc<Mutex<BackendStatus>>,
}

impl BackendManager {
    pub fn new(metadata_path: PathBuf) -> Self {
        Self {
            child: Mutex::new(None),
            metadata_path,
            status: Arc::new(Mutex::new(BackendStatus {
                phase: "stopped".into(),
                message: "Backend has not started".into(),
                url: None,
                recent_output: Vec::new(),
            })),
        }
    }

    pub fn start(
        &self,
        app: AppHandle,
        paths: &RuntimePaths,
        lm_model: &str,
    ) -> Result<(), String> {
        let stale_metadata = self.metadata_path.exists();
        self.stop();
        let port = reserve_port()?;
        let secret = launch_secret()?;
        let port_arg = port.to_string();
        let output_arg = paths.outputs.to_string_lossy().into_owned();
        let checkpoints_arg = paths.checkpoints.to_string_lossy().into_owned();
        let logs_arg = paths.logs.to_string_lossy().into_owned();
        let mut command = Command::new(backend_command());
        command
            .args([
                "--port",
                &port_arg,
                "--launch-secret",
                &secret,
                "--output-dir",
                &output_arg,
                "--checkpoints-dir",
                &checkpoints_arg,
                "--log-dir",
                &logs_arg,
                "--lm-model",
                lm_model,
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                let message = format!("backend spawn failed: {error}");
                self.fail(&app, &message);
                return Err(message);
            }
        };
        if let Some(stdout) = child.stdout.take() {
            capture_output(app.clone(), self.status.clone(), stdout);
        }
        if let Some(stderr) = child.stderr.take() {
            capture_output(app.clone(), self.status.clone(), stderr);
        }
        let metadata = serde_json::json!({"pid": child.id(), "port": port});
        if let Err(error) = std::fs::write(&self.metadata_path, metadata.to_string()) {
            let _ = child.kill();
            let _ = child.wait();
            let message = format!("runtime metadata write failed: {error}");
            self.fail(&app, &message);
            return Err(message);
        }
        *self.child.lock().map_err(|_| "backend lock poisoned")? = Some(child);
        update_status(&app, &self.status, "starting", "Loading models", None);
        if stale_metadata {
            append_diagnostic(&app, &self.status, "Removed stale runtime metadata");
        }
        let status = self.status.clone();
        thread::spawn(move || poll_readiness(app, status, port, secret));
        Ok(())
    }

    pub fn stop(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
        let _ = std::fs::remove_file(&self.metadata_path);
    }

    pub fn status(&self) -> BackendStatus {
        self.status
            .lock()
            .map(|value| value.clone())
            .unwrap_or_else(|_| BackendStatus {
                phase: "failed".into(),
                message: "Backend state lock failed".into(),
                url: None,
                recent_output: Vec::new(),
            })
    }

    pub fn diagnostics(&self) -> String {
        serde_json::to_string_pretty(&self.status()).unwrap_or_else(|error| error.to_string())
    }

    pub fn fail(&self, app: &AppHandle, message: &str) {
        update_status(app, &self.status, "failed", message, None);
    }
}

fn capture_output<R: Read + Send + 'static>(
    app: AppHandle,
    status: Arc<Mutex<BackendStatus>>,
    output: R,
) {
    thread::spawn(move || {
        for line in BufReader::new(output).lines().map_while(Result::ok) {
            if let Ok(mut current) = status.lock() {
                current.recent_output.push(line);
                if current.recent_output.len() > 50 {
                    current.recent_output.remove(0);
                }
                let _ = app.emit("backend-status", current.clone());
            }
        }
    });
}

fn append_diagnostic(app: &AppHandle, status: &Arc<Mutex<BackendStatus>>, line: &str) {
    if let Ok(mut current) = status.lock() {
        current.recent_output.push(line.into());
        let _ = app.emit("backend-status", current.clone());
    }
}

pub(crate) fn reserve_port() -> Result<u16, String> {
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|socket| socket.local_addr())
        .map(|address| address.port())
        .map_err(|error| format!("port allocation failed: {error}"))
}

pub(crate) fn launch_secret() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut file| file.read_exact(&mut bytes))
        .map_err(|error| format!("secret generation failed: {error}"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

pub(crate) fn backend_command() -> String {
    if cfg!(debug_assertions) {
        std::env::var("ACESTEP_DESKTOP_COMMAND").unwrap_or_else(|_| "acestep-desktop".into())
    } else {
        "/app/bin/acestep-desktop".into()
    }
}
