"""Tests for atomic desktop model preparation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from acestep.desktop_model_manager import DEFAULT_LM, SMALL_LM, install_models, model_status


def _write_weights(directory: Path, component: str) -> None:
    """Create the minimum weight marker used by model validation."""
    target = directory / component
    target.mkdir(parents=True, exist_ok=True)
    (target / "model.safetensors").write_bytes(b"weights")


class DesktopModelManagerTest(unittest.TestCase):
    """Cover installation status, capacity checks, and atomic activation."""

    def test_status_reports_existing_model_set_ready(self) -> None:
        """A complete selected model set supports offline startup."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for component in (
                "acestep-v15-turbo",
                "vae",
                "Qwen3-Embedding-0.6B",
                DEFAULT_LM,
            ):
                _write_weights(root, component)

            status = model_status(root)

        self.assertTrue(status.ready)
        self.assertEqual(status.required_bytes, 0)

    @patch("acestep.desktop_model_manager.shutil.disk_usage")
    def test_install_rejects_insufficient_space(self, disk_usage) -> None:
        """Downloads do not begin when the destination lacks capacity."""
        disk_usage.return_value = SimpleNamespace(free=1)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(OSError, "Insufficient disk space"):
                install_models(Path(temporary), downloader=lambda **_: "")

    def test_install_stages_and_activates_selected_small_lm(self) -> None:
        """Verified staged components are promoted and staging remains resumable."""
        calls: list[str] = []

        def download(**kwargs: object) -> str:
            local_dir = Path(str(kwargs["local_dir"]))
            calls.append(str(kwargs["repo_id"]))
            patterns = kwargs.get("allow_patterns")
            if patterns:
                for pattern in patterns:
                    _write_weights(local_dir, str(pattern).split("/")[0])
            else:
                _write_weights(local_dir.parent, local_dir.name)
            return str(local_dir)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = install_models(root, SMALL_LM, downloader=download)

            self.assertTrue(status.ready)
            self.assertTrue((root / SMALL_LM / "model.safetensors").exists())
            self.assertTrue((root / ".download").is_dir())
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
