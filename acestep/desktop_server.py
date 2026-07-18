"""Restricted CLI bootstrap for the ACE-Step Tauri desktop backend."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

from acestep.desktop_model_manager import DEFAULT_LM, install_models, model_status
from acestep.runtime_paths import ensure_directory, get_log_dir


def build_parser() -> argparse.ArgumentParser:
    """Build the desktop-only argument parser."""
    parser = argparse.ArgumentParser(description="ACE-Step desktop backend")
    parser.add_argument("--port", type=int)
    parser.add_argument("--launch-secret")
    parser.add_argument("--output-dir")
    parser.add_argument("--checkpoints-dir")
    parser.add_argument("--log-dir")
    parser.add_argument("--language", default="en")
    parser.add_argument("--model-action", choices=("status", "install"))
    parser.add_argument("--lm-model", default=DEFAULT_LM)
    return parser


def emit_startup_event(phase: str, **details: object) -> None:
    """Write a machine-readable lifecycle event for the Tauri parent process."""
    print(json.dumps({"event": "acestep.desktop", "phase": phase, **details}), flush=True)


def main(argv: list[str] | None = None) -> None:
    """Validate desktop configuration and launch Gradio on loopback only."""
    args = build_parser().parse_args(argv)
    if args.model_action:
        _run_model_action(args.model_action, args.checkpoints_dir, args.lm_model)
        return
    if args.port is None or args.launch_secret is None:
        raise SystemExit("--port and --launch-secret are required for backend startup")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not args.launch_secret.strip():
        raise SystemExit("--launch-secret must not be empty")

    if args.log_dir:
        os.environ["ACESTEP_LOG_DIR"] = args.log_dir
    if args.output_dir:
        os.environ["ACESTEP_OUTPUT_DIR"] = args.output_dir
    if args.checkpoints_dir:
        os.environ["ACESTEP_CHECKPOINTS_DIR"] = args.checkpoints_dir
    log_dir = ensure_directory(get_log_dir())
    _configure_file_logging(log_dir)

    os.environ["ACESTEP_DESKTOP_LAUNCH_SECRET"] = args.launch_secret
    pipeline_args = [
        "acestep-desktop",
        "--server-name",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--enable-api",
        "--api-key",
        args.launch_secret,
        "--language",
        args.language,
        "--service_mode",
        "true",
    ]
    _append_path_argument(pipeline_args, "--output-dir", args.output_dir)
    _append_path_argument(pipeline_args, "--checkpoints-dir", args.checkpoints_dir)
    pipeline_args.extend(("--lm_model_path", args.lm_model))

    emit_startup_event("launching", host="127.0.0.1", port=args.port)
    with _pipeline_argv(pipeline_args):
        _run_pipeline()


def _run_model_action(action: str, checkpoints_dir: str | None, lm_model: str) -> None:
    """Run a desktop model action and emit its JSON result."""
    if not checkpoints_dir:
        raise SystemExit("--checkpoints-dir is required for model actions")
    directory = Path(checkpoints_dir)
    status = (
        install_models(directory, lm_model)
        if action == "install"
        else model_status(directory, lm_model)
    )
    print(json.dumps(status.to_dict()), flush=True)


def _run_pipeline() -> None:
    """Import and run the existing pipeline only after desktop validation."""
    from acestep.acestep_v15_pipeline import main as pipeline_main

    pipeline_main()


def _configure_file_logging(log_dir: Path) -> None:
    """Add bounded, rotating desktop backend logs."""
    logger.add(
        log_dir / "backend.log",
        rotation="10 MB",
        retention=5,
        enqueue=True,
    )


def _append_path_argument(arguments: list[str], name: str, value: str | None) -> None:
    """Append an optional path argument without exposing generic passthrough flags."""
    if value:
        arguments.extend((name, value))


@contextmanager
def _pipeline_argv(arguments: list[str]) -> Iterator[None]:
    """Temporarily replace process arguments for the existing pipeline CLI."""
    original = sys.argv
    sys.argv = arguments
    try:
        yield
    finally:
        sys.argv = original


if __name__ == "__main__":
    main()
