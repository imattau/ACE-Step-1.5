"""Manage first-run model installation for the packaged desktop application."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from acestep.model_downloader import _contains_model_weights, _sync_model_code_files

MAIN_REPO = "ACE-Step/Ace-Step1.5"
DEFAULT_LM = "acestep-5Hz-lm-1.7B"
SMALL_LM = "acestep-5Hz-lm-0.6B"
CORE_COMPONENTS = ("acestep-v15-turbo", "vae", "Qwen3-Embedding-0.6B")
LM_REPOS = {DEFAULT_LM: MAIN_REPO, SMALL_LM: "ACE-Step/acestep-5Hz-lm-0.6B"}
DOWNLOAD_BYTES = {DEFAULT_LM: 10_100_000_000, SMALL_LM: 7_200_000_000}


@dataclass(frozen=True)
class ModelStatus:
    """Describe the selected desktop model installation."""

    ready: bool
    lm_model: str
    installed: tuple[str, ...]
    missing: tuple[str, ...]
    required_bytes: int
    free_bytes: int
    checkpoints_dir: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable status mapping."""
        return asdict(self)


def model_status(checkpoints_dir: Path, lm_model: str = DEFAULT_LM) -> ModelStatus:
    """Inspect required components and available disk space.

    Args:
        checkpoints_dir: Private desktop checkpoint directory.
        lm_model: Selected language model directory name.

    Returns:
        Current installation and capacity state.

    Raises:
        ValueError: If the language model is unsupported.
    """
    _validate_lm(lm_model)
    components = (*CORE_COMPONENTS, lm_model)
    installed = tuple(
        component
        for component in components
        if _contains_model_weights(checkpoints_dir / component)
    )
    missing = tuple(component for component in components if component not in installed)
    probe = checkpoints_dir if checkpoints_dir.exists() else checkpoints_dir.parent
    free_bytes = shutil.disk_usage(probe).free
    return ModelStatus(
        ready=not missing,
        lm_model=lm_model,
        installed=installed,
        missing=missing,
        required_bytes=0 if not missing else DOWNLOAD_BYTES[lm_model],
        free_bytes=free_bytes,
        checkpoints_dir=str(checkpoints_dir),
    )


def install_models(
    checkpoints_dir: Path,
    lm_model: str = DEFAULT_LM,
    downloader: Callable[..., str] | None = None,
) -> ModelStatus:
    """Resume, verify, and atomically activate the selected model set.

    Args:
        checkpoints_dir: Private desktop checkpoint directory.
        lm_model: Selected supported language model.
        downloader: Injectable Hugging Face snapshot function for tests.

    Returns:
        Ready model status after activation.

    Raises:
        OSError: If insufficient space remains.
        RuntimeError: If a downloaded component lacks model weights.
        ValueError: If the language model is unsupported.
    """
    before = model_status(checkpoints_dir, lm_model)
    if before.ready:
        return before
    if before.free_bytes < before.required_bytes:
        raise OSError(
            f"Insufficient disk space: need {before.required_bytes} bytes, "
            f"have {before.free_bytes} bytes"
        )
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    staging = checkpoints_dir / ".download"
    staging.mkdir(exist_ok=True)
    download = downloader or _snapshot_download
    main_components = [component for component in before.missing if component in CORE_COMPONENTS]
    if lm_model == DEFAULT_LM and lm_model in before.missing:
        main_components.append(lm_model)
    if main_components:
        patterns = [f"{component}/**" for component in main_components]
        download(repo_id=MAIN_REPO, local_dir=str(staging), allow_patterns=patterns)
        _activate(staging, checkpoints_dir, main_components)
        if "acestep-v15-turbo" in main_components:
            _sync_model_code_files("acestep-v15-turbo", checkpoints_dir)
    if lm_model == SMALL_LM and lm_model in before.missing:
        lm_staging = staging / lm_model
        download(repo_id=LM_REPOS[lm_model], local_dir=str(lm_staging))
        _activate(staging, checkpoints_dir, [lm_model])
    after = model_status(checkpoints_dir, lm_model)
    if not after.ready:
        raise RuntimeError(f"Model verification failed: missing {', '.join(after.missing)}")
    return after


def _activate(staging: Path, destination: Path, components: list[str]) -> None:
    """Verify staged components before moving them into the live directory."""
    for component in components:
        if not _contains_model_weights(staging / component):
            raise RuntimeError(f"Downloaded component has no model weights: {component}")
    for component in components:
        target = destination / component
        if target.exists():
            shutil.rmtree(target)
        (staging / component).replace(target)


def _snapshot_download(**kwargs: object) -> str:
    """Download a resumable Hugging Face snapshot into its staging directory."""
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def _validate_lm(lm_model: str) -> None:
    """Reject language models not offered by the desktop first-run flow."""
    if lm_model not in LM_REPOS:
        raise ValueError(f"Unsupported language model: {lm_model}")
