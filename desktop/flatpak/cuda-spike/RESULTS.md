# CUDA spike results

## 2026-07-18 development-host run

Status: **preliminary go; second driver validation pending**

The diagnostic implementation and deterministic unit tests pass. The installed
Flatpak successfully used its active NVIDIA driver extension and completed a real
CUDA operation, despite the same host reporting CUDA unavailable outside Flatpak.

Observed environment:

```text
Architecture: x86_64
Flatpak: 1.16.6
Freedesktop Platform: 25.08
PyTorch: 2.10.0+cu128
PyTorch bundled CUDA: 12.8
torch.cuda.is_available(): false
nvidia-smi: unable to communicate with the NVIDIA driver
flatpak-builder: 1.4.2
```

Installed graphics extensions include:

```text
org.freedesktop.Platform.GL.default//25.08
org.freedesktop.Platform.GL.default//25.08-extra
org.freedesktop.Platform.GL.nvidia-580-159-03//1.4
org.freedesktop.Platform.GL.nvidia-580-173-02//1.4
org.freedesktop.Platform.VAAPI.nvidia//25.08
```

Host probe result:

```json
{"event":"cuda_probe","status":"cuda_unavailable","torch":{"cuda_available":false,"cuda_built":"12.8","hip_built":null,"version":"2.10.0+cu128"}}
```

The host probe returned exit code 3, the documented `cuda_unavailable` result. The
installed Flatpak used `org.freedesktop.Platform.GL.nvidia-580-173-02` and returned:

```json
{"audio":{"soundfile":"0.13.1","torchaudio":"2.10.0+cu128"},"cuda_operation":{"expected":32.0,"result":32.0},"device":{"capability":[12,0],"index":0,"memory_bytes":16608788480,"name":"NVIDIA GeForce RTX 5060 Ti"},"event":"cuda_probe","runtime":{"flatpak":true,"flatpak_id":"ai.acestep.ACEStep.CudaProbe","machine":"x86_64","python":"3.13.14"},"status":"ok","torch":{"cuda_available":true,"cuda_built":"12.8","hip_built":null,"version":"2.10.0+cu128"}}
```

The installed probe returned exit code 0 with both its original `--device=all`
permission and an explicit `--nodevice=all --device=dri` override. The checked-in
manifest now uses only `--device=dri`.

The Flatpak was built entirely from locked wheel URLs and hashes and installed as a
user application. Its installed size is approximately 7 GB. That size is acceptable
for the boundary spike but requires dependency deduplication and cleanup before a
production package.

## Evidence still required

1. Repeat the installed-Flatpak test on a second supported NVIDIA driver version.
2. Repeat the `--device=dri` test on an older supported GPU architecture.
3. Package Python 3.12 for the production app; the boundary probe uses the
   Freedesktop 25.08 runtime's Python 3.13.
4. Replace the PyPI boundary-probe wheel with ACE-Step's exact custom-index pin in
   the production dependency manifest.

The first required driver test is a go: CUDA and native audio work inside Flatpak with
DRI-only device permission. The final gate remains open until a second supported
driver version reproduces the result.
