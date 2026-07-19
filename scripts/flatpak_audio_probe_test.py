"""Tests for the deterministic Flatpak audio probe."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.flatpak_audio_probe import CODECS, run_probe


class FlatpakAudioProbeTest(unittest.TestCase):
    """Verify codec failures and no-device operation are reported correctly."""

    def test_all_codec_round_trips_succeed_without_audio_device(self) -> None:
        """Headless support does not depend on a PulseAudio socket."""
        with tempfile.TemporaryDirectory() as temporary:
            report = run_probe(_successful_run, Path(temporary))

        self.assertTrue(report["all_codecs"])
        self.assertFalse(report["pulse_socket"])
        self.assertTrue(report["headless_supported"])
        self.assertEqual(set(report["codecs"]), set(CODECS))

    def test_failed_encoder_marks_only_affected_codec(self) -> None:
        """An unavailable encoder produces an actionable failed capability."""
        def fail_mp3(arguments, **kwargs):
            return subprocess.CompletedProcess(arguments, 1 if "libmp3lame" in arguments else 0)

        with tempfile.TemporaryDirectory() as temporary:
            report = run_probe(fail_mp3, Path(temporary))

        self.assertFalse(report["all_codecs"])
        self.assertFalse(report["codecs"]["mp3"])
        self.assertTrue(report["codecs"]["wav"])


def _successful_run(arguments, **kwargs):
    """Return a successful subprocess result for probe unit tests."""
    return subprocess.CompletedProcess(arguments, 0)


if __name__ == "__main__":
    unittest.main()
