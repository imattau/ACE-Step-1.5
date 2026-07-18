//! Resolve private XDG locations passed to the packaged Python backend.

use std::{env, fs, io, path::PathBuf};

#[derive(Clone, Debug)]
pub struct RuntimePaths {
    pub checkpoints: PathBuf,
    pub logs: PathBuf,
    pub outputs: PathBuf,
    pub runtime_metadata: PathBuf,
}

impl RuntimePaths {
    pub fn resolve() -> io::Result<Self> {
        let data = xdg_base("XDG_DATA_HOME", ".local/share").join("ace-step");
        let state = xdg_base("XDG_STATE_HOME", ".local/state").join("ace-step");
        let paths = Self {
            checkpoints: data.join("checkpoints"),
            logs: state.join("logs"),
            outputs: data.join("outputs"),
            runtime_metadata: state.join("desktop-runtime.json"),
        };
        for path in [&paths.checkpoints, &paths.logs, &paths.outputs] {
            fs::create_dir_all(path)?;
        }
        Ok(paths)
    }
}

fn xdg_base(variable: &str, fallback: &str) -> PathBuf {
    env::var_os(variable).map(PathBuf::from).unwrap_or_else(|| {
        PathBuf::from(env::var_os("HOME").unwrap_or_else(|| "/tmp".into())).join(fallback)
    })
}
