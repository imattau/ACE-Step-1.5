"""Acceptance tests for the Flatpak sandbox permission set.

Every Flatpak permission in the stable manifest must have a documented
rationale and be validated by an acceptance test.
"""

import unittest
from pathlib import Path


MANIFEST_PATH = Path(__file__).parents[1] / "ai.acestep.ACEStep.yaml"


def _parse_finish_args(path: Path) -> list[str]:
    """Extract the finish-args list from a Flatpak YAML manifest.

    This avoids a pyyaml dependency by doing a minimal line-oriented parse
    of the finish-args block.
    """
    args: list[str] = []
    in_finish_args = False
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped == "finish-args:":
                in_finish_args = True
                continue
            if in_finish_args:
                if stripped == "":
                    continue
                if not stripped.startswith("#") and not stripped.startswith("- "):
                    break
                if stripped.startswith("- "):
                    args.append(stripped[2:])
    return args


class FlatpakPermissionTest(unittest.TestCase):
    """Verify the Flatpak manifest uses the minimal proven permission set."""

    @classmethod
    def setUpClass(cls):
        cls.finish_args = _parse_finish_args(MANIFEST_PATH)

    def test_no_host_filesystem_access(self):
        """Must not request broad home or host filesystem access."""
        for arg in self.finish_args:
            self.assertNotIn("--filesystem=home", arg)
            self.assertNotIn("--filesystem=host", arg)
            self.assertNotIn("--filesystem=/", arg)

    def test_no_device_all(self):
        """--device=all must not be required after CUDA feasibility validation."""
        for arg in self.finish_args:
            self.assertNotIn("--device=all", arg)

    def test_minimal_network_permission(self):
        """Must use --share=network (not the broader --share=all)."""
        self.assertIn("--share=network", self.finish_args)

    def test_ipc_shared(self):
        """--share=ipc is required for WebKit and portal communication."""
        self.assertIn("--share=ipc", self.finish_args)

    def test_display_sockets_configured(self):
        """Both Wayland and X11 fallback sockets must be available."""
        self.assertIn("--socket=wayland", self.finish_args)
        self.assertIn("--socket=fallback-x11", self.finish_args)

    def test_audio_socket_configured(self):
        """PulseAudio socket is required for WebKit audio playback."""
        self.assertIn("--socket=pulseaudio", self.finish_args)

    def test_dri_device_available(self):
        """DRM device access is required for GPU compute via DRI."""
        self.assertIn("--device=dri", self.finish_args)

    def test_no_unexpected_permissions(self):
        """Only the documented finish-args should be present."""
        expected = {
            "--share=network",
            "--share=ipc",
            "--socket=wayland",
            "--socket=fallback-x11",
            "--socket=pulseaudio",
            "--device=dri",
        }
        actual = set(self.finish_args)
        unexpected = actual - expected
        self.assertEqual(
            set(),
            unexpected,
            f"Unexpected permission(s) found: {unexpected}",
        )


if __name__ == "__main__":
    unittest.main()
