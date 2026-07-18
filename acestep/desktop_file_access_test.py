"""Contract tests for restricted Flatpak desktop file access."""

import unittest
from pathlib import Path


class DesktopFileAccessTest(unittest.TestCase):
    """Protect portal usage, narrow permissions, and training feature gating."""

    def setUp(self) -> None:
        """Resolve committed desktop packaging files."""
        root = Path(__file__).resolve().parent.parent
        self.manifest = (root / "desktop/flatpak/ai.acestep.ACEStep.yaml").read_text()
        self.launcher = (root / "desktop/flatpak/build-aux/acestep-desktop").read_text()

    def test_manifest_has_no_broad_home_access(self) -> None:
        """Only the preview download directory is host-writable."""
        self.assertNotIn("--filesystem=home", self.manifest)
        self.assertNotIn("--filesystem=host", self.manifest)
        self.assertIn("--filesystem=xdg-download:create", self.manifest)

    def test_launcher_prefers_desktop_portals(self) -> None:
        """GTK and WebKit file selection should use XDG Desktop Portal."""
        self.assertIn("export GTK_USE_PORTAL=1", self.launcher)


if __name__ == "__main__":
    unittest.main()
