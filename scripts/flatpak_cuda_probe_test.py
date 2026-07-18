"""Unit tests for the Flatpak CUDA feasibility probe."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.flatpak_cuda_probe import (
    EXIT_AUDIO_IMPORT_FAILED,
    EXIT_CUDA_OPERATION_FAILED,
    EXIT_CUDA_UNAVAILABLE,
    EXIT_SUCCESS,
    run_probe,
)


def _torch_stub(cuda_available: bool = True) -> MagicMock:
    """Create a torch-compatible stub for probe tests."""

    torch = MagicMock()
    torch.__version__ = "2.10.0+cu128"
    torch.version = SimpleNamespace(cuda="12.8", hip=None)
    torch.cuda.is_available.return_value = cuda_available
    torch.cuda.get_device_properties.return_value = SimpleNamespace(total_memory=24 * 1024**3)
    torch.cuda.get_device_capability.return_value = (8, 9)
    torch.cuda.get_device_name.return_value = "Test GPU"
    result = MagicMock()
    result.item.return_value = 32.0
    torch.tensor.return_value.__mul__.return_value.sum.return_value = result
    return torch


class FlatpakCudaProbeTest(unittest.TestCase):
    """Verify stable feasibility outcomes without requiring a physical GPU."""

    @patch("scripts.flatpak_cuda_probe.importlib.import_module")
    def test_success_reports_cuda_and_audio_details(self, import_module: MagicMock) -> None:
        """A real CUDA operation and native audio imports should pass the gate."""

        import_module.side_effect = [
            SimpleNamespace(__version__="0.13.1"),
            SimpleNamespace(__version__="2.10.0+cu128"),
        ]

        report, exit_code = run_probe(_torch_stub())

        self.assertEqual(EXIT_SUCCESS, exit_code)
        self.assertEqual("ok", report["status"])
        self.assertEqual(32.0, report["cuda_operation"]["result"])
        self.assertEqual("Test GPU", report["device"]["name"])

    def test_unavailable_cuda_fails_before_allocation(self) -> None:
        """A CUDA wheel without an accessible GPU should fail the gate clearly."""

        torch = _torch_stub(cuda_available=False)

        report, exit_code = run_probe(torch)

        self.assertEqual(EXIT_CUDA_UNAVAILABLE, exit_code)
        self.assertEqual("cuda_unavailable", report["status"])
        torch.tensor.assert_not_called()

    def test_kernel_failure_has_distinct_exit_code(self) -> None:
        """Driver or kernel failures should not be reported as missing CUDA."""

        torch = _torch_stub()
        torch.tensor.side_effect = RuntimeError("kernel failed")

        report, exit_code = run_probe(torch)

        self.assertEqual(EXIT_CUDA_OPERATION_FAILED, exit_code)
        self.assertEqual("cuda_operation_failed", report["status"])

    @patch("scripts.flatpak_cuda_probe.importlib.import_module")
    def test_audio_import_failure_fails_after_cuda_success(self, import_module: MagicMock) -> None:
        """Missing packaged native audio modules should fail the feasibility gate."""

        import_module.side_effect = OSError("libsndfile missing")

        report, exit_code = run_probe(_torch_stub())

        self.assertEqual(EXIT_AUDIO_IMPORT_FAILED, exit_code)
        self.assertEqual("audio_import_failed", report["status"])


if __name__ == "__main__":
    unittest.main()
