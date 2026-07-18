//! ACE-Step Tauri application lifecycle.

mod backend;
#[cfg(test)]
mod backend_test;
mod models;
mod paths;
mod readiness;

use backend::BackendManager;
use paths::RuntimePaths;
use std::sync::Mutex;
use tauri::{Manager, State};

struct DesktopState {
    backend: BackendManager,
    paths: RuntimePaths,
    lm_model: Mutex<String>,
}

#[tauri::command]
fn retry_backend(app: tauri::AppHandle, state: State<'_, DesktopState>) -> Result<(), String> {
    let lm_model = state.lm_model.lock().map_err(|_| "model lock poisoned")?;
    state.backend.start(app, &state.paths, &lm_model)
}

#[tauri::command]
fn backend_status(state: State<'_, DesktopState>) -> backend::BackendStatus {
    state.backend.status()
}

#[tauri::command]
fn backend_diagnostics(state: State<'_, DesktopState>) -> String {
    state.backend.diagnostics()
}

#[tauri::command]
fn model_status(
    state: State<'_, DesktopState>,
    lm_model: Option<String>,
) -> Result<models::ModelStatus, String> {
    let selected = state.lm_model.lock().map_err(|_| "model lock poisoned")?;
    models::inspect(
        &state.paths.checkpoints,
        lm_model.as_deref().unwrap_or(&selected),
    )
}

#[tauri::command]
fn install_models(
    app: tauri::AppHandle,
    state: State<'_, DesktopState>,
    lm_model: String,
) -> Result<models::ModelStatus, String> {
    let status = models::install(&state.paths.checkpoints, &lm_model)?;
    models::save_selection(&state.paths.model_manifest, &lm_model)?;
    *state.lm_model.lock().map_err(|_| "model lock poisoned")? = lm_model.clone();
    state.backend.start(app, &state.paths, &lm_model)?;
    Ok(status)
}

#[tauri::command]
fn quit_app(app: tauri::AppHandle) {
    app.exit(0);
}

#[tauri::command]
fn open_logs(state: State<'_, DesktopState>) -> Result<(), String> {
    std::process::Command::new("xdg-open")
        .arg(&state.paths.logs)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("failed to open log directory: {error}"))
}

fn main() {
    let paths = RuntimePaths::resolve().expect("failed to create private runtime directories");
    let backend = BackendManager::new(paths.runtime_metadata.clone());
    let lm_model = Mutex::new(models::load_selection(&paths.model_manifest));
    tauri::Builder::default()
        .manage(DesktopState {
            backend,
            paths,
            lm_model,
        })
        .invoke_handler(tauri::generate_handler![
            backend_status,
            backend_diagnostics,
            model_status,
            install_models,
            retry_backend,
            open_logs,
            quit_app,
        ])
        .setup(|app| {
            let state = app.state::<DesktopState>();
            let lm_model = state
                .lm_model
                .lock()
                .map(|value| value.clone())
                .unwrap_or_default();
            if models::inspect(&state.paths.checkpoints, &lm_model)
                .map(|status| status.ready)
                .unwrap_or(false)
            {
                let _ = state
                    .backend
                    .start(app.handle().clone(), &state.paths, &lm_model);
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build ACE-Step desktop shell")
        .run(|app, event| {
            if matches!(
                event,
                tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
            ) {
                app.state::<DesktopState>().backend.stop();
            }
        });
}
