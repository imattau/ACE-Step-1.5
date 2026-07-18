# Flatpak CUDA feasibility spike

This package is the first go/no-go gate for the Linux Tauri build. It verifies that
the installed Flatpak can import the packaged CUDA build of PyTorch, access the host
NVIDIA driver extension, execute a real CUDA kernel, synchronize it, and import the
native audio stack.

## Current prerequisites

- Linux x86_64
- Flatpak and `flatpak-builder`
- Flathub configured
- Freedesktop SDK and Platform 25.08
- A working proprietary NVIDIA driver
- The matching `org.freedesktop.Platform.GL.nvidia-*` extension
- A generated `python3-ace-step-cuda-probe.json` containing locked Python sources

The generated Python module is deliberately not handwritten. PyTorch's CUDA wheel
has a large native dependency graph, and every source needs a stable URL and hash for
an offline, reviewable Flatpak build. This boundary probe uses Python 3.13 from the
Freedesktop 25.08 runtime. ACE-Step currently requires Python 3.11-3.12, so the
production Flatpak must add a separately packaged Python 3.12 runtime after this GPU
boundary has been proven.

The spike uses the PyPI Linux PyTorch wheel because the official Flatpak generator
cannot resolve metadata from PyTorch's custom `+cu128` index. Both distributions pull
the CUDA user-space dependency set; the probe records the actual bundled CUDA version
so the result remains explicit. The production dependency manifest must use the exact
project-pinned wheel source.

## Run the host baseline

```bash
uv run python scripts/flatpak_cuda_probe.py
```

The host baseline must return status `ok` before a Flatpak result can demonstrate
sandbox compatibility.

## Build and run

```bash
flatpak-builder --user --install-deps-from=flathub --force-clean \
  --install build-dir desktop/flatpak/cuda-spike/ai.acestep.ACEStep.CudaProbe.yaml
flatpak run ai.acestep.ACEStep.CudaProbe
```

The probe prints exactly one JSON diagnostic line. Exit code zero and status `ok`
are required for a go decision.

## Permission comparison

The spike was first built with `--device=all`, then run with
`--nodevice=all --device=dri`. Both executions completed the CUDA operation. The
checked-in manifest therefore retains only `--device=dri`. Repeat this comparison on
new GPU/driver families before expanding the supported matrix.

## Decision rule

Go requires successful installed-Flatpak runs on at least two supported NVIDIA driver
versions without using host Python or host CUDA user-space libraries. A missing or
mismatched driver must produce structured `cuda_unavailable` or
`cuda_operation_failed` output rather than crashing.

The result is no-go if real CUDA operations require unsupported host-library access,
cannot work with the Flatpak NVIDIA extension, or require permissions unacceptable for
distribution. A machine without a working host NVIDIA driver cannot make the final
decision; it can only validate the failure diagnostics.

Recorded development-host results and remaining evidence are maintained in
[`RESULTS.md`](RESULTS.md).

## Runtime path validation

The installed probe can also validate the Phase 2 path adapter while mounting the
repository read-only:

```bash
flatpak run --filesystem="$PWD:ro" --command=python3 \
  ai.acestep.ACEStep.CudaProbe \
  "$PWD/scripts/flatpak_runtime_paths_probe.py" "$PWD"
```

Success requires `status: ok`, a rejected write beneath the mounted repository, and
all reported mutable directories beneath Flatpak's private XDG locations.
