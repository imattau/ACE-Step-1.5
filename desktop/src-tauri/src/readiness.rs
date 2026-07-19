//! Poll the authenticated backend readiness endpoint on loopback.

use std::{
    io::{Read, Write},
    net::TcpStream,
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};

use tauri::{AppHandle, Emitter};

use crate::backend::BackendStatus;

pub fn poll_readiness(
    app: AppHandle,
    status: Arc<Mutex<BackendStatus>>,
    port: u16,
    secret: String,
) {
    for _ in 0..600 {
        thread::sleep(Duration::from_millis(500));
        if probe(port, &secret) {
            let url = format!("http://127.0.0.1:{port}");
            update_status(&app, &status, "ready", "ACE-Step is ready", Some(url));
            return;
        }
    }
    update_status(
        &app,
        &status,
        "failed",
        "Backend readiness timed out",
        None,
    );
}

pub fn update_status(
    app: &AppHandle,
    status: &Arc<Mutex<BackendStatus>>,
    phase: &str,
    message: &str,
    url: Option<String>,
) {
    if let Ok(mut current) = status.lock() {
        current.phase = phase.into();
        current.message = message.into();
        current.url = url;
        let _ = app.emit("backend-status", current.clone());
    }
}

fn probe(port: u16, secret: &str) -> bool {
    let address = format!("127.0.0.1:{port}")
        .parse()
        .expect("valid loopback address");
    let Ok(mut stream) =
        TcpStream::connect_timeout(&address, Duration::from_millis(250))
    else {
        return false;
    };
    let request = format!(
        "GET /desktop/ready HTTP/1.1\r\nHost: 127.0.0.1\r\nX-ACEStep-Launch-Secret: {secret}\r\nConnection: close\r\n\r\n"
    );
    let mut response = String::new();
    stream.write_all(request.as_bytes()).is_ok()
        && stream.read_to_string(&mut response).is_ok()
        && response.starts_with("HTTP/1.1 200")
        && response.contains("\"ready\":true")
}
