"""Unit tests for the restricted desktop backend bootstrap."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acestep import desktop_server


class DesktopServerTests(unittest.TestCase):
    """Verify safe argument construction and runtime directory setup."""

    def test_main_forces_loopback_and_desktop_security_flags(self) -> None:
        """The desktop wrapper should expose no public binding or sharing controls."""
        captured: list[str] = []
        captured_environment: dict[str, str | None] = {}

        def pipeline_main() -> None:
            captured.extend(sys.argv)
            captured_environment["secret"] = os.environ.get("ACESTEP_DESKTOP_LAUNCH_SECRET")

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {},
            clear=True,
        ), patch.object(desktop_server, "_run_pipeline", side_effect=pipeline_main), patch(
            "acestep.desktop_server.logger.add"
        ):
            desktop_server.main(
                [
                    "--port",
                    "8765",
                    "--launch-secret",
                    "launch-token",
                    "--log-dir",
                    str(Path(temp_dir) / "logs"),
                ]
            )

        self.assertEqual("127.0.0.1", captured[captured.index("--server-name") + 1])
        self.assertIn("--enable-api", captured)
        self.assertNotIn("--share", captured)
        self.assertEqual("launch-token", captured_environment["secret"])

    def test_main_rejects_empty_secret(self) -> None:
        """An empty per-launch secret must stop before server startup."""
        with self.assertRaisesRegex(SystemExit, "must not be empty"):
            desktop_server.main(["--port", "8765", "--launch-secret", " "])

    def test_parser_rejects_unrecognized_public_server_flags(self) -> None:
        """Desktop mode must not accept host, share, or arbitrary path flags."""
        with self.assertRaises(SystemExit):
            desktop_server.build_parser().parse_args(
                ["--port", "8765", "--launch-secret", "secret", "--share"]
            )


if __name__ == "__main__":
    unittest.main()
