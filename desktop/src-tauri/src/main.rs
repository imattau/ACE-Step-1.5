//! ACE-Step Tauri application lifecycle.

mod backend;
#[cfg(test)]
mod backend_test;
mod paths;
mod readiness;

use backend::BackendManager;
use paths::RuntimePaths;
use tauri::{Manager, State};

struct DesktopState {
    backend: BackendManager,
    paths: RuntimePaths,
}

#[tauri::command]
fn retry_backend(app: tauri::AppHandle, state: State<'_, DesktopState>) -> Result<(), String> {
    state.backend.start(app, &state.paths)
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
    tauri::Builder::default()
        .manage(DesktopState { backend, paths })
        .invoke_handler(tauri::generate_handler![
            backend_status,
            backend_diagnostics,
            retry_backend,
            open_logs,
            quit_app,
        ])
        .setup(|app| {
            let state = app.state::<DesktopState>();
            let _ = state.backend.start(app.handle().clone(), &state.paths);
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
