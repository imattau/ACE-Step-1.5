"""Run the CUDA and native-audio checks required by the Flatpak feasibility gate."""

from __future__ import annotations

import importlib
import json
import os
import platform
import sys
from collections.abc import Sequence
from typing import Any

EXIT_SUCCESS = 0
EXIT_TORCH_IMPORT_FAILED = 2
EXIT_CUDA_UNAVAILABLE = 3
EXIT_CUDA_OPERATION_FAILED = 4
EXIT_AUDIO_IMPORT_FAILED = 5

AUDIO_MODULES = ("soundfile", "torchaudio")


def _error_details(error: Exception) -> dict[str, str]:
    """Return stable, JSON-safe details for a probe failure."""

    return {"error_type": type(error).__name__, "error": str(error)}


def _runtime_details() -> dict[str, Any]:
    """Collect runtime details useful when diagnosing a Flatpak installation."""

    return {
        "flatpak": bool(os.environ.get("FLATPAK_ID")),
        "flatpak_id": os.environ.get("FLATPAK_ID"),
        "flatpak_gl_drivers": os.environ.get("FLATPAK_GL_DRIVERS"),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def run_probe(torch_module: Any | None = None) -> tuple[dict[str, Any], int]:
    """Run import, CUDA allocation, kernel, synchronization, and audio checks.

    Args:
        torch_module: Optional injected torch-compatible module for deterministic tests.

    Returns:
        A tuple containing the structured diagnostic and process exit code.
    """

    report: dict[str, Any] = {"event": "cuda_probe", "runtime": _runtime_details()}

    if torch_module is None:
        try:
            torch_module = importlib.import_module("torch")
        except (ImportError, OSError) as error:
            report.update({"status": "torch_import_failed", **_error_details(error)})
            return report, EXIT_TORCH_IMPORT_FAILED

    report["torch"] = {
        "version": str(torch_module.__version__),
        "cuda_built": getattr(torch_module.version, "cuda", None),
        "hip_built": getattr(torch_module.version, "hip", None),
    }

    try:
        cuda_available = bool(torch_module.cuda.is_available())
    except (OSError, RuntimeError) as error:
        report.update({"status": "cuda_check_failed", **_error_details(error)})
        return report, EXIT_CUDA_UNAVAILABLE

    report["torch"]["cuda_available"] = cuda_available
    if not cuda_available:
        report["status"] = "cuda_unavailable"
        return report, EXIT_CUDA_UNAVAILABLE

    try:
        properties = torch_module.cuda.get_device_properties(0)
        report["device"] = {
            "capability": list(torch_module.cuda.get_device_capability(0)),
            "index": 0,
            "memory_bytes": int(properties.total_memory),
            "name": str(torch_module.cuda.get_device_name(0)),
        }
        left = torch_module.tensor([1.0, 2.0, 3.0], device="cuda")
        right = torch_module.tensor([4.0, 5.0, 6.0], device="cuda")
        result = (left * right).sum()
        torch_module.cuda.synchronize()
        report["cuda_operation"] = {"expected": 32.0, "result": float(result.item())}
        if report["cuda_operation"]["result"] != 32.0:
            raise RuntimeError("CUDA kernel returned an unexpected result")
    except (OSError, RuntimeError) as error:
        report.update({"status": "cuda_operation_failed", **_error_details(error)})
        return report, EXIT_CUDA_OPERATION_FAILED

    audio_versions: dict[str, str] = {}
    try:
        for module_name in AUDIO_MODULES:
            module = importlib.import_module(module_name)
            audio_versions[module_name] = str(getattr(module, "__version__", "unknown"))
    except (ImportError, OSError) as error:
        report["audio"] = audio_versions
        report.update({"status": "audio_import_failed", **_error_details(error)})
        return report, EXIT_AUDIO_IMPORT_FAILED

    report["audio"] = audio_versions
    report["status"] = "ok"
    return report, EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    """Print the Flatpak CUDA diagnostic as one JSON line and return its exit code.

    Args:
        argv: Reserved command-line arguments for forward compatibility.

    Returns:
        Zero when CUDA and audio checks pass; a stable nonzero diagnostic code otherwise.
    """

    del argv
    report, exit_code = run_probe()
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
