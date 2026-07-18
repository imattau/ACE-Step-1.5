"""Tests for target-specific Flatpak wheel source generation."""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("pylock_to_flatpak.py")
SPEC = importlib.util.spec_from_file_location("pylock_to_flatpak", MODULE_PATH)
assert SPEC and SPEC.loader
pylock_to_flatpak = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pylock_to_flatpak)


class PylockToFlatpakTest(unittest.TestCase):
    """Validate marker and wheel selection for the Linux desktop target."""

    def test_build_module_selects_compatible_locked_wheel(self) -> None:
        """Use the compatible wheel URL and checksum in the generated source."""
        lock = {
            "packages": [
                {
                    "name": "example",
                    "version": "1.0",
                    "wheels": [
                        {
                            "url": "https://example.test/example-1.0-py3-none-any.whl",
                            "hashes": {"sha256": "abc123"},
                        }
                    ],
                }
            ]
        }

        module = pylock_to_flatpak.build_module(lock)

        self.assertEqual(module["sources"][0]["sha256"], "abc123")
        self.assertEqual(
            module["sources"][0]["dest-filename"], "example-1.0-py3-none-any.whl"
        )

    def test_build_module_ignores_non_target_marker(self) -> None:
        """Exclude packages whose markers do not match Linux Python 3.12."""
        lock = {
            "packages": [
                {
                    "name": "windows-only",
                    "version": "1.0",
                    "marker": "sys_platform == 'win32'",
                    "wheels": [],
                }
            ]
        }

        module = pylock_to_flatpak.build_module(lock)

        self.assertEqual(module["sources"], [])

    def test_select_wheel_rejects_incompatible_artifacts(self) -> None:
        """Reject a package without a target-compatible wheel."""
        package = {
            "name": "wrong-platform",
            "wheels": [
                {
                    "url": "https://example.test/wrong_platform-1.0-cp312-cp312-win_amd64.whl",
                    "hashes": {"sha256": "abc123"},
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "No CPython 3.12 Linux x86_64 wheel"):
            pylock_to_flatpak.select_wheel(package)


if __name__ == "__main__":
    unittest.main()
