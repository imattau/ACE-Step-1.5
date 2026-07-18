# Tauri Desktop Build Plan

## Goal

Package ACE-Step as a Tauri desktop application, with Linux x86_64 Flatpak as the
first and reference platform. The initial hardware target is NVIDIA CUDA, with a
CPU fallback included only if it does not materially complicate the package.

The desktop application will preserve the existing Gradio interface and Python
inference stack. Tauri will provide the native window, backend lifecycle management,
startup diagnostics, and desktop integration.

## First-release scope

In scope:

- Linux x86_64 Flatpak
- NVIDIA CUDA inference
- Existing Gradio user interface
- Python backend managed by Tauri
- First-run model download
- Audio generation and playback
- Portal-based file import and export
- Sandbox-aware logging and diagnostics
- CPU fallback if validated during the feasibility spike

Deferred:

- AMD ROCm
- Intel XPU
- Linux aarch64
- macOS and Windows packages
- Replacing Gradio with a native frontend
- Broad access to the host filesystem
- Training flows that cannot operate through Flatpak portals
- Automatic discovery of models in arbitrary host directories

## Proposed architecture

```text
Flatpak sandbox
|-- Tauri desktop process
|-- WebKit webview
|-- Python 3.11 runtime installed under /app
|-- ACE-Step and PyTorch/CUDA user-space libraries
`-- Gradio server bound to 127.0.0.1
    |-- models  -> $XDG_DATA_HOME/ace-step/checkpoints
    |-- outputs -> $XDG_DATA_HOME/ace-step/outputs
    |-- cache   -> $XDG_CACHE_HOME/ace-step
    `-- logs    -> $XDG_STATE_HOME/ace-step/logs
```

Flatpak maps these XDG locations beneath the application's private directory at
`~/.var/app/<flatpak-app-id>/`. The installed `/app` tree is read-only, so no model,
configuration, cache, log, or generated output may be written there.

Python should initially be installed directly under `/app` by the Flatpak build. It
should not be wrapped with PyInstaller or Nuitka unless direct packaging proves
unworkable. Tauri will launch a fixed `/app/bin/acestep-desktop` command as a managed
child process.

## Runtime contract

Tauri and the Python backend will use a small, explicit contract:

1. Tauri resolves and creates the application XDG directories.
2. Tauri generates an unpredictable secret for the launch.
3. Tauri starts `/app/bin/acestep-desktop` with explicit data paths and the secret.
4. Python binds only to `127.0.0.1` on a dynamically assigned port.
5. Python emits machine-readable startup events on standard output.
6. Tauri shows a startup screen while it waits for backend readiness.
7. Tauri opens the Gradio URL only after the backend reports readiness.
8. Tauri requests graceful shutdown on exit and force-terminates only after a short
   timeout.

Example backend arguments:

```text
--server-name 127.0.0.1
--port 0
--data-dir <xdg-data>/ace-step
--checkpoints-dir <xdg-data>/ace-step/checkpoints
--output-dir <xdg-data>/ace-step/outputs
--cache-dir <xdg-cache>/ace-step
--log-dir <xdg-state>/ace-step/logs
--desktop-mode
--launch-token <secret>
```

Example startup events:

```json
{"event":"starting"}
{"event":"checking_runtime"}
{"event":"checking_models"}
{"event":"loading_models"}
{"event":"ready","url":"http://127.0.0.1:49321"}
{"event":"failed","code":"cuda_unavailable","message":"..."}
```

The backend should bind to port `0` and report the assigned port if Gradio/Uvicorn
can support that safely. If not, use bounded bind retries and distinct error codes.
Two application instances must never connect to each other's backend.

## Phase 1: CUDA-in-Flatpak feasibility spike

GPU access is the highest-risk assumption and must be proven before building the
complete desktop application.

Create a minimal Flatpak that:

1. Imports the packaged PyTorch build.
2. Reports the PyTorch and bundled CUDA versions.
3. Evaluates `torch.cuda.is_available()`.
4. Identifies the GPU and available VRAM.
5. Allocates a CUDA tensor and runs a small kernel.
6. Imports the native audio dependencies used by ACE-Step.
7. Produces structured diagnostics for success and failure.

Test it with:

- A current NVIDIA proprietary driver
- An older supported driver baseline
- Wayland and X11
- A CPU-only system
- A missing or mismatched Flatpak NVIDIA driver extension
- An unsupported host driver

Start with the narrowest plausible permissions:

```yaml
finish-args:
  - --share=network
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --device=dri
```

Add `--device=all` only if an actual CUDA compute test proves it necessary. Record
the result and justification because this permission is broader and may affect
Flathub review.

Acceptance criteria:

- A clean Flatpak installation performs a real CUDA operation.
- It does not use host Python, a host virtual environment, or host CUDA user-space
  libraries.
- Missing driver support produces an actionable diagnostic instead of a crash.

## Phase 2: Runtime path foundation

Status: **In progress (foundation and primary startup consumers complete).**

Implemented:

- Central Flatpak/XDG path resolution in `acestep/runtime_paths.py`.
- Explicit `--output-dir` and `--checkpoints-dir` startup overrides.
- Flatpak-safe output and checkpoint defaults in the main pipeline and model downloader.
- Focused coverage for precedence, native defaults, Unicode/spaces, missing state XDG,
  and invalid file paths.

Remaining before Phase 2 is closed:

- Route the disk cache and API lifespan cache through the central resolver.
- Route result/file-serving defaults through the resolved output directory.
- Verify startup with the application files mounted read-only in the Flatpak harness.

Add a focused module such as `acestep/runtime_paths.py` to resolve:

- Application data directory
- Checkpoint directory
- Output directory
- Cache directory
- Log directory
- Configuration directory

Resolution priority:

1. Explicit command-line argument
2. Dedicated `ACESTEP_*` environment variable
3. XDG directory when running under Flatpak
4. Existing repository-relative behavior outside Flatpak

Keep Flatpak detection behind the path adapter rather than adding conditionals
throughout inference code. Update only consumers that assume the source tree or
working directory is writable, including the pipeline, model downloader, output
initialization, and file-serving routes.

Tests must cover:

- Explicit path overrides
- Environment overrides
- XDG resolution under Flatpak
- Existing non-Flatpak defaults
- Missing `XDG_STATE_HOME`
- Read-only application directories
- Paths containing spaces and Unicode
- A file supplied where a directory is required

## Phase 3: Desktop Python bootstrap

Add a focused `acestep/desktop_server.py` module and the entry point:

```toml
acestep-desktop = "acestep.desktop_server:main"
```

Responsibilities:

- Parse desktop-specific arguments.
- Validate and create runtime directories.
- Configure rotating file logs.
- Bind Gradio strictly to loopback.
- Disable sharing and browser launch.
- Register health and readiness endpoints.
- Emit structured startup events.
- Implement graceful shutdown.
- Authenticate desktop-only endpoints with the launch secret.

Desktop mode must reject:

- Binding to `0.0.0.0`
- Gradio sharing
- Public URLs
- Arbitrary filesystem-serving paths
- Multiple server workers

Health and readiness must be separate. Health means the server is alive; readiness
means initialization is complete and the UI can be displayed.

## Phase 4: Tauri shell

Add a self-contained desktop tree:

```text
desktop/
|-- package.json
|-- src/
|   |-- startup.ts
|   `-- diagnostics.ts
|-- src-tauri/
|   |-- Cargo.toml
|   |-- tauri.conf.json
|   `-- src/
|       |-- main.rs
|       |-- paths.rs
|       |-- backend.rs
|       `-- readiness.rs
`-- flatpak/
    |-- <app-id>.yaml
    |-- <app-id>.desktop
    |-- <app-id>.metainfo.xml
    |-- requirements-generated.json
    `-- build-aux/
```

Keep modules focused and within the repository's module-size policy where practical.

Tauri responsibilities:

- Resolve XDG paths supplied by Flatpak.
- Start only the fixed packaged backend command.
- Pass paths and the launch secret explicitly.
- Capture and parse backend output.
- Display startup phases and actionable failures.
- Poll authenticated health and readiness endpoints.
- Navigate to Gradio only after readiness.
- Shut down and reap the backend process on exit.
- Detect stale runtime metadata from its own previous launches.
- Offer Retry, Open Logs, Copy Diagnostics, and Quit actions.

Do not expose generic shell execution to content loaded in the webview.

## Phase 5: Reproducible Flatpak build

Select a current, supported Freedesktop or GNOME runtime compatible with Tauri's
WebKit requirements and pin its branch.

Build modules in this order:

1. Native libraries absent from the selected runtime
2. Locked Python dependencies
3. ACE-Step Python package
4. Rust/Tauri application
5. Desktop metadata, icons, and launcher

Build requirements:

- Pin every downloadable source and include its checksum.
- Generate Python source modules with `flatpak-pip-generator` or an equivalent
  locked-source workflow.
- Vendor or explicitly declare Rust and JavaScript sources.
- Do not run `uv sync`, Cargo, npm, or pip against the live internet during the
  actual Flatpak build.
- Do not include `.venv` or local checkpoints.
- Do not bundle NVIDIA host driver libraries.
- Install application files under `/app`.
- Remove tests, headers, caches, and development metadata from the final artifact.
- Reproduce the build from a clean source checkout without host dependencies.

Validate that the existing Linux PyTorch CUDA dependency works with the matching
Flatpak NVIDIA driver extension.

## Phase 6: Model management

Do not include the approximately 9.4 GB model set in the Flatpak artifact. Store
models under `$XDG_DATA_HOME/ace-step/checkpoints` and use the existing Python model
downloader behind a small service boundary.

First-run flow:

1. List required and optional model components.
2. Display download sizes and destination.
3. Allow selection of the language-model size where supported.
4. Check available disk space before downloading.
5. Download into a staging directory.
6. Resume interrupted downloads where supported.
7. Verify upstream checksums when available.
8. Atomically promote completed components.
9. Preserve completed models across application updates.
10. Start offline when all required models are already present.

Do not use Flatpak `extra-data` for the initial implementation. Application-managed
downloads give better control over optional components, progress, resumption, and
model updates.

Keep application, runtime, and model versions separate in a data manifest:

```json
{
  "desktopSchema": 1,
  "appVersion": "1.5.0",
  "runtimeVariant": "linux-flatpak-cuda-x86_64",
  "models": {}
}
```

## Phase 7: File access and portals

Do not request `--filesystem=home`.

- Keep models, configuration, logs, and default outputs in private XDG directories.
- Import source audio and datasets through desktop document portals.
- Export generated audio through the save-file portal.
- Investigate portal-backed persistent access before supporting an external model
  directory.
- Feature-gate training in the first Flatpak release if its directory workflows
  cannot work safely through portals.

A preview may temporarily request narrowly scoped access such as
`--filesystem=xdg-music:create`, but stable release should prefer portal-based export.

## Phase 8: Audio integration

Package and test the audio codecs and native libraries required by ACE-Step. Support:

- Playback through PipeWire/PulseAudio compatibility
- Generated-audio playback from the local Gradio server
- Portal-based audio import and export
- Operation without an available audio output device
- Headless generation where possible

Request only the audio socket required by the selected runtime and WebKit stack.

## Phase 9: Security hardening

The stable Flatpak manifest should keep the smallest proven permission set. A
candidate is:

```yaml
finish-args:
  - --share=network
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --socket=pulseaudio
  - --device=dri
```

Retain `--device=all` only if the CUDA spike demonstrates that it is unavoidable.

Application controls:

- Loopback-only backend
- Per-launch authentication secret
- Restrictive Tauri capabilities
- No generic shell execution
- No full-home permission
- Allowlisted file-serving directories
- Path traversal protection
- Sanitized backend errors
- Secrets excluded from logs
- A content security policy appropriate for local Gradio content

Every Flatpak permission must have a documented reason and an acceptance test.

## Phase 10: Diagnostics and support

The diagnostics screen should report:

- ACE-Step and desktop versions
- Flatpak ID and runtime branch
- Kernel and CPU architecture
- PyTorch and bundled CUDA versions
- Detected NVIDIA driver and Flatpak graphics extensions
- `torch.cuda.is_available()` result
- GPU name and VRAM
- Selected inference backend
- XDG data locations
- Model installation state
- Backend startup phase
- Sanitized recent errors

Write rotating logs to:

```text
$XDG_STATE_HOME/ace-step/logs/desktop.log
$XDG_STATE_HOME/ace-step/logs/backend.log
```

An exported diagnostics archive must not contain prompts, generated audio, model
files, credentials, or the launch secret.

## Testing matrix

Automated tests:

- Python runtime-path unit tests
- Desktop bootstrap unit tests
- Rust backend-lifecycle tests
- TypeScript startup-state tests
- Flatpak manifest validation
- Offline clean Flatpak build
- Permission inspection
- Backend process shutdown and crash-recovery tests
- CPU smoke test
- CUDA smoke test on a GPU runner when available

Clean-system testing:

- Ubuntu, Fedora, and one rolling distribution
- Wayland and X11
- Current and minimum-supported NVIDIA drivers
- Missing or mismatched NVIDIA Flatpak extension
- CPU-only machine
- Fresh, interrupted, and resumed model downloads
- Online and offline startup
- Application upgrade and reinstall
- Unicode filenames and user paths
- Generation, playback, import, and export
- Backend crash and application restart
- Two simultaneous application instances

## Delivery milestones

### Milestone 1: CUDA feasibility

- Minimal Flatpak manifest
- Packaged Python and PyTorch
- Successful CUDA kernel
- Driver-extension diagnostics
- Documented permission requirements

Do not commit to the complete package until this passes on at least two NVIDIA
driver versions.

### Milestone 2: Runtime paths

- XDG-aware path resolver
- Backward-compatible source and CLI behavior
- Focused Python unit tests

### Milestone 3: Desktop backend

- Desktop entry point
- Loopback-only Gradio server
- Health and readiness protocol
- Structured logs and events
- Authentication and shutdown tests

### Milestone 4: Development Tauri application

- Backend lifecycle management
- Startup and failure UI
- Gradio webview
- Portal proof of concept
- Development Flatpak

### Milestone 5: Reproducible complete Flatpak

- Locked Python, Rust, and JavaScript sources
- ACE-Step installed under `/app`
- No dependency on host Python or `.venv`
- Clean offline build

### Milestone 6: Model manager

- Download size and disk-space checks
- Progress and resumption
- Verification and atomic activation
- Correct offline behavior

### Milestone 7: Linux preview

- Signed Flatpak repository artifact
- Installation and troubleshooting documentation
- Diagnostics export
- Published permissions rationale
- NVIDIA compatibility matrix

### Milestone 8: Flathub readiness

- Complete AppStream metadata
- Screenshots and release metadata
- License and source declarations
- Reproducible source manifest
- Minimal sandbox permissions
- Resolution of Flathub review findings

## Release acceptance criteria

The Linux Flatpak is ready for stable release when:

- A non-administrator can install and launch it on a clean supported system.
- CUDA generation works using only packaged user-space libraries and the matching
  Flatpak driver extension.
- Missing GPU support produces an actionable error or validated CPU fallback.
- First-run model download is explicit, resumable, and space-checked.
- Existing models allow offline startup.
- Generation and audio playback work under Wayland and X11.
- Import and export work through portals without full-home access.
- Outputs and models survive application upgrades.
- Exiting the application releases the port and GPU memory.
- A backend crash does not leave a persistent child process.
- Multiple instances cannot connect to each other's backend.
- Existing non-Flatpak CLI, API, Gradio, and hardware behavior remains unchanged.
- The package builds reproducibly from declared sources without a host virtual
  environment.

## Principal risks

1. **CUDA device access:** prove real compute in the sandbox before broader work.
2. **NVIDIA driver compatibility:** provide explicit diagnostics and a tested support
   baseline.
3. **Python dependency size:** exclude models and remove build-only content.
4. **Dynamic Python imports and native libraries:** validate them in an installed
   Flatpak, not only in the build environment.
5. **Gradio lifecycle:** separate health from model readiness and guarantee backend
   cleanup.
6. **Filesystem assumptions:** route every mutable path to an explicit XDG location.
7. **Portal limitations:** feature-gate workflows that would otherwise require broad
   host access.

The CUDA feasibility spike is the first implementation task and the primary go/no-go
gate for the Linux Flatpak architecture.
