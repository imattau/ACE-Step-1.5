"""Tests for Flatpak build settings outside the sandbox permission set."""

import unittest
from pathlib import Path


MANIFEST_PATH = Path(__file__).parents[1] / "ai.acestep.ACEStep.yaml"


class FlatpakManifestTest(unittest.TestCase):
    """Verify release-only requirements remain enabled in packaged builds."""

    def test_tauri_release_uses_custom_protocol(self) -> None:
        """The webview must load bundled assets instead of the Vite development URL."""
        manifest = MANIFEST_PATH.read_text()

        self.assertIn("--features tauri/custom-protocol", manifest)


if __name__ == "__main__":
    unittest.main()
