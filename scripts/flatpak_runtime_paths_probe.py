"""Validate ACE-Step runtime directories from a read-only Flatpak source mount."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    """Resolve writable directories and verify the mounted application is read-only."""
    if len(sys.argv) != 2:
        print(json.dumps({"status": "invalid_arguments"}))
        return 2

    application_root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(application_root))

    from acestep.runtime_paths import (
        ensure_directory,
        get_cache_dir,
        get_checkpoints_dir,
        get_config_dir,
        get_log_dir,
        get_output_dir,
    )

    directories = {
        "cache": get_cache_dir(application_root),
        "checkpoints": get_checkpoints_dir(legacy_root=application_root),
        "config": get_config_dir(application_root),
        "logs": get_log_dir(application_root),
        "outputs": get_output_dir(legacy_root=application_root),
    }
    try:
        for path in directories.values():
            ensure_directory(path)
        _verify_read_only(application_root)
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "application_root": str(application_root),
                "directories": {name: str(path) for name, path in directories.items()},
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_read_only(application_root: Path) -> None:
    """Raise when the application mount unexpectedly permits a new file."""
    probe_path = application_root / ".acestep-flatpak-write-probe"
    try:
        probe_path.touch(exist_ok=False)
    except OSError:
        return
    probe_path.unlink(missing_ok=True)
    raise OSError(f"Application root is writable: {application_root}")


if __name__ == "__main__":
    raise SystemExit(main())
