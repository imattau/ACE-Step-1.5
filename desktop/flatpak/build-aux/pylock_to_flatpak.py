#!/usr/bin/env python3
"""Generate a Linux x86_64 Flatpak wheel module from a PEP 751 lock file."""

import argparse
import json
import os
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlparse

from packaging.markers import Marker
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename


TARGET_ENVIRONMENT = {
    "implementation_name": "cpython",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "python_full_version": "3.12.13",
    "python_version": "3.12",
    "sys_platform": "linux",
}


def package_applies(package: dict[str, object]) -> bool:
    """Return whether a locked package applies to the Flatpak target."""
    marker = package.get("marker")
    return marker is None or Marker(str(marker)).evaluate(TARGET_ENVIRONMENT)


def select_wheel(package: dict[str, object]) -> dict[str, object]:
    """Select the first wheel compatible with the build host and target."""
    supported_tags = set(sys_tags())
    for wheel in package.get("wheels", []):
        filename = unquote(Path(urlparse(str(wheel["url"])).path).name)
        _, _, _, wheel_tags = parse_wheel_filename(filename)
        if supported_tags.intersection(wheel_tags):
            return wheel
    raise ValueError(f"No CPython 3.12 Linux x86_64 wheel for {package['name']}")


def wheel_source(wheel: dict[str, object]) -> dict[str, str]:
    """Convert a locked wheel into a checksummed Flatpak file source."""
    url = str(wheel["url"])
    return {
        "type": "file",
        "url": url,
        "sha256": str(wheel["hashes"]["sha256"]),
        "dest-filename": unquote(Path(urlparse(url).path).name),
    }


def build_module(lock: dict[str, object]) -> dict[str, object]:
    """Build the Flatpak module for all applicable locked wheels."""
    packages = [package for package in lock["packages"] if package_applies(package)]
    sources = [wheel_source(select_wheel(package)) for package in packages]
    return {
        "name": "python3-ace-step-dependencies",
        "buildsystem": "simple",
        "build-commands": [
            "/app/lib/ace-step-python/bin/python3.12 -m pip install --verbose "
            "--no-index --no-deps --find-links=file://${PWD} "
            "--prefix=/app/lib/ace-step-python ./*.whl"
        ],
        "sources": sources,
    }


def main() -> None:
    """Parse arguments and write the generated Flatpak module."""
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.lock.open("rb") as lock_file:
        module = build_module(tomllib.load(lock_file))
    args.output.write_text(json.dumps(module, indent=2) + os.linesep)


if __name__ == "__main__":
    main()
