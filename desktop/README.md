# ACE-Step desktop shell

This directory contains the Linux-first Tauri v2 shell. The webview receives only
Tauri core IPC permissions; backend process spawning, readiness authentication, log
opening, and shutdown remain in Rust.

## Development checks

```bash
npm install
npm run build
source "$HOME/.cargo/env"
cargo check --manifest-path src-tauri/Cargo.toml
```

To run against the development Python entry point, set the fixed debug-only command
override before starting Tauri:

```bash
ACESTEP_DESKTOP_COMMAND="../.venv/bin/acestep-desktop" npm run tauri dev
```

Release builds ignore `ACESTEP_DESKTOP_COMMAND` and execute only
`/app/bin/acestep-desktop`, which the production Flatpak must install.

The Rust parent allocates a loopback port, generates a per-launch secret, passes
private XDG directories to Python, polls the authenticated readiness route, and
reaps the backend when the application exits.
