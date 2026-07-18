"""Resolve writable ACE-Step runtime directories across packaging environments."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

_APP_DIRECTORY = "ace-step"


class RuntimePathError(ValueError):
    """Report that a configured runtime directory cannot be used."""


def is_flatpak(environment: Mapping[str, str] | None = None) -> bool:
    """Return whether the process is running in a Flatpak sandbox."""
    env = os.environ if environment is None else environment
    return bool(env.get("FLATPAK_ID"))


def get_checkpoints_dir(
    explicit: str | os.PathLike[str] | None = None,
    legacy_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the model checkpoint directory without creating it."""
    return _resolve_directory(
        explicit,
        "ACESTEP_CHECKPOINTS_DIR",
        "data",
        "checkpoints",
        _legacy_child(legacy_root, "checkpoints"),
    )


def get_output_dir(
    explicit: str | os.PathLike[str] | None = None,
    legacy_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the generated-output directory without creating it."""
    return _resolve_directory(
        explicit,
        "ACESTEP_OUTPUT_DIR",
        "data",
        "outputs",
        _legacy_child(legacy_root, "gradio_outputs"),
    )


def get_cache_dir(
    legacy_root: str | os.PathLike[str] | None = None,
    legacy_child: str = ".cache",
) -> Path:
    """Resolve the application cache directory without creating it."""
    return _resolve_directory(
        None,
        "ACESTEP_CACHE_DIR",
        "cache",
        None,
        _legacy_child(legacy_root, legacy_child),
    )


def get_log_dir(legacy_root: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the application log directory without creating it."""
    return _resolve_directory(
        None,
        "ACESTEP_LOG_DIR",
        "state",
        "logs",
        _legacy_child(legacy_root, "logs"),
    )


def get_config_dir(legacy_root: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the application configuration directory without creating it."""
    return _resolve_directory(
        None,
        "ACESTEP_CONFIG_DIR",
        "config",
        None,
        _legacy_child(legacy_root, "config"),
    )


def ensure_directory(path: Path) -> Path:
    """Create a runtime directory or raise an actionable configuration error."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimePathError(f"Cannot create runtime directory '{path}': {exc}") from exc
    if not path.is_dir():
        raise RuntimePathError(f"Runtime path is not a directory: '{path}'")
    return path


def _legacy_child(root: str | os.PathLike[str] | None, child: str) -> Path:
    """Return a child of the supplied legacy application root."""
    return Path.cwd() / child if root is None else Path(root) / child


def _resolve_directory(
    explicit: str | os.PathLike[str] | None,
    environment_name: str,
    xdg_kind: str,
    child: str | None,
    legacy_default: Path,
) -> Path:
    """Apply explicit, environment, Flatpak XDG, then legacy precedence."""
    configured = explicit or os.environ.get(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    if not is_flatpak():
        return legacy_default
    base = _xdg_base(xdg_kind) / _APP_DIRECTORY
    return base if child is None else base / child


def _xdg_base(kind: str) -> Path:
    """Return an XDG base directory with the freedesktop default fallback."""
    defaults = {
        "data": Path.home() / ".local" / "share",
        "cache": Path.home() / ".cache",
        "state": Path.home() / ".local" / "state",
        "config": Path.home() / ".config",
    }
    configured = os.environ.get(f"XDG_{kind.upper()}_HOME")
    return Path(configured).expanduser() if configured else defaults[kind]
