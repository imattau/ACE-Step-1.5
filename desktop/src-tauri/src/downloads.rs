//! Route WebKit downloads through the native save-file portal.

use std::path::{Path, PathBuf};

use gtk::prelude::{FileChooserExt, NativeDialogExt};
use gtk::{FileChooserAction, FileChooserNative, ResponseType};
use tauri::webview::DownloadEvent;

pub fn handle_download(event: DownloadEvent<'_>) -> bool {
    match event {
        DownloadEvent::Requested { url, destination } => {
            let suggested = suggested_name(url.path(), destination);
            let dialog = FileChooserNative::new(
                Some("Save generated file"),
                None::<&gtk::Window>,
                FileChooserAction::Save,
                Some("Save"),
                Some("Cancel"),
            );
            dialog.set_current_name(&suggested);
            dialog.set_do_overwrite_confirmation(true);
            if dialog.run() != ResponseType::Accept {
                return false;
            }
            match dialog.filename() {
                Some(path) if path.is_absolute() => {
                    *destination = path;
                    true
                }
                _ => false,
            }
        }
        DownloadEvent::Finished { .. } => true,
        _ => true,
    }
}

fn suggested_name(url_path: &str, destination: &Path) -> String {
    destination
        .file_name()
        .and_then(|name| name.to_str().map(str::to_owned))
        .or_else(|| {
            PathBuf::from(url_path)
                .file_name()
                .and_then(|name| name.to_str())
                .map(str::to_owned)
        })
        .filter(|name| !name.is_empty())
        .unwrap_or_else(|| "ace-step-output".into())
}

#[cfg(test)]
mod tests {
    use super::suggested_name;
    use std::path::Path;

    #[test]
    fn destination_filename_has_priority() {
        assert_eq!(
            suggested_name("/file=other.wav", Path::new("/tmp/generated.wav")),
            "generated.wav"
        );
    }

    #[test]
    fn missing_filename_uses_safe_fallback() {
        assert_eq!(suggested_name("/", Path::new("/")), "ace-step-output");
    }
}
