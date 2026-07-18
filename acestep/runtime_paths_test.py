"""Unit tests for Flatpak-aware ACE-Step runtime path resolution."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acestep.runtime_paths import (
    RuntimePathError,
    ensure_directory,
    get_cache_dir,
    get_checkpoints_dir,
    get_log_dir,
    get_output_dir,
)


class RuntimePathsTests(unittest.TestCase):
    """Verify runtime path precedence and validation."""

    def test_explicit_path_overrides_environment(self) -> None:
        """An explicit path has the highest resolution priority."""
        with patch.dict(os.environ, {"ACESTEP_OUTPUT_DIR": "/ignored"}, clear=True):
            result = get_output_dir("/chosen path")
        self.assertEqual(Path("/chosen path"), result)

    def test_environment_path_overrides_flatpak_xdg(self) -> None:
        """A dedicated environment override takes priority over XDG."""
        env = {"FLATPAK_ID": "ai.acestep.ACEStep", "ACESTEP_CHECKPOINTS_DIR": "/models"}
        with patch.dict(os.environ, env, clear=True):
            result = get_checkpoints_dir()
        self.assertEqual(Path("/models"), result)

    def test_flatpak_uses_xdg_data_directories(self) -> None:
        """Flatpak outputs and checkpoints use the application data root."""
        env = {"FLATPAK_ID": "ai.acestep.ACEStep", "XDG_DATA_HOME": "/data home/用户"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(Path("/data home/用户/ace-step/outputs"), get_output_dir())
            self.assertEqual(Path("/data home/用户/ace-step/checkpoints"), get_checkpoints_dir())

    def test_non_flatpak_preserves_legacy_defaults(self) -> None:
        """Native launches retain repository-relative directory defaults."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Path("/repo/gradio_outputs"), get_output_dir(legacy_root="/repo"))
            self.assertEqual(Path("/repo/checkpoints"), get_checkpoints_dir(legacy_root="/repo"))

    def test_missing_xdg_state_home_uses_standard_fallback(self) -> None:
        """Flatpak logs fall back to the freedesktop state location."""
        with patch.dict(os.environ, {"FLATPAK_ID": "ai.acestep.ACEStep"}, clear=True):
            self.assertEqual(Path.home() / ".local/state/ace-step/logs", get_log_dir())

    def test_flatpak_cache_ignores_read_only_application_tree(self) -> None:
        """A sandbox launch should create cache data only beneath writable XDG storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            application_root = root / "app"
            application_root.mkdir()
            application_root.chmod(0o555)
            cache_home = root / "cache home"
            env = {
                "FLATPAK_ID": "ai.acestep.ACEStep",
                "XDG_CACHE_HOME": str(cache_home),
            }
            try:
                with patch.dict(os.environ, env, clear=True):
                    result = ensure_directory(get_cache_dir(application_root))
                    self.assertTrue(result.is_dir())
            finally:
                application_root.chmod(0o755)

        self.assertEqual(cache_home / "ace-step", result)

    def test_ensure_directory_rejects_a_file(self) -> None:
        """A configured file produces an actionable directory error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "not-a-directory"
            file_path.write_text("content", encoding="utf-8")
            with self.assertRaisesRegex(RuntimePathError, "not a directory|Cannot create"):
                ensure_directory(file_path)


if __name__ == "__main__":
    unittest.main()
