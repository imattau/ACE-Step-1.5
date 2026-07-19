#!/app/lib/ace-step-python/bin/python3.12
"""Probe ACE-Step audio codecs and headless behavior inside the Flatpak sandbox."""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path

CODECS = {
    "wav": ("pcm_s16le", "wav"),
    "flac": ("flac", "flac"),
    "mp3": ("libmp3lame", "mp3"),
    "ogg": ("libvorbis", "ogg"),
    "opus": ("libopus", "opus"),
    "m4a": ("aac", "ipod"),
}


def run_probe(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    runtime_dir: Path | None = None,
) -> dict[str, object]:
    """Run codec round trips and report whether an audio socket is present.

    Args:
        runner: Injectable subprocess runner used by tests.
        runtime_dir: Runtime directory containing the PulseAudio socket.

    Returns:
        JSON-compatible codec and headless capability report.
    """
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "source.wav"
        _write_tone(source)
        codecs = {
            name: _round_trip(source, root / f"output.{name}", codec, container, runner)
            for name, (codec, container) in CODECS.items()
        }
    pulse_root = runtime_dir or Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/0"))
    pulse_socket = (pulse_root / "pulse/native").is_socket()
    return {
        "codecs": codecs,
        "all_codecs": all(codecs.values()),
        "pulse_socket": pulse_socket,
        "headless_supported": True,
    }


def _round_trip(
    source: Path,
    output: Path,
    codec: str,
    container: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    """Encode and decode one format through the packaged FFmpeg binary."""
    encode = runner(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-c:a",
            codec,
            "-f",
            container,
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if encode.returncode != 0:
        return False
    decode = runner(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if decode.returncode != 0:
        return False
    playback = runner(
        [
            "gst-launch-1.0",
            "-q",
            "filesrc",
            f"location={output}",
            "!",
            "decodebin",
            "!",
            "audioconvert",
            "!",
            "fakesink",
        ],
        capture_output=True,
        text=True,
    )
    return playback.returncode == 0


def _write_tone(path: Path) -> None:
    """Write a short deterministic mono PCM tone for codec tests."""
    sample_rate = 16_000
    frames = [
        struct.pack("<h", int(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
        for index in range(sample_rate // 10)
    ]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(frames))


def main() -> None:
    """Print the audio capability report and fail only for missing codecs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = run_probe()
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["all_codecs"] else 1)


if __name__ == "__main__":
    main()
