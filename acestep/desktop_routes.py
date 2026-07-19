"""Register authenticated lifecycle endpoints for the Tauri desktop shell."""

from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import APIRouter, Header, HTTPException


def register_desktop_routes(
    app: object,
    launch_secret: str,
    is_ready: Callable[[], bool],
    diagnostics_provider: Callable[[], dict[str, object]] | None = None,
) -> None:
    """Add secret-protected desktop health and readiness endpoints.

    Args:
        app: FastAPI-compatible application receiving the router.
        launch_secret: Per-launch secret shared only with the Tauri process.
        is_ready: Callback reporting whether model initialization completed.
        diagnostics_provider: Optional callback returning Python-side
            diagnostics (PyTorch version, GPU info, model state, etc.).

    Raises:
        ValueError: If the launch secret is empty.
    """
    if not launch_secret:
        raise ValueError("Desktop launch secret must not be empty")

    router = APIRouter(prefix="/desktop")

    def authenticate(x_acestep_launch_secret: str | None = Header(default=None)) -> None:
        """Reject requests that do not carry the per-launch secret."""
        if not x_acestep_launch_secret or not secrets.compare_digest(
            x_acestep_launch_secret,
            launch_secret,
        ):
            raise HTTPException(status_code=401, detail="Invalid desktop launch secret")

    @router.get("/health")
    async def health(
        x_acestep_launch_secret: str | None = Header(default=None),
    ) -> dict[str, str]:
        """Report that the desktop backend HTTP process is alive."""
        authenticate(x_acestep_launch_secret)
        return {"status": "ok"}

    @router.get("/ready")
    async def readiness(
        x_acestep_launch_secret: str | None = Header(default=None),
    ) -> dict[str, bool | str]:
        """Report whether initialization is complete and the UI may be shown."""
        authenticate(x_acestep_launch_secret)
        ready = is_ready()
        return {"status": "ready" if ready else "starting", "ready": ready}

    @router.get("/diagnostics")
    async def diagnostics(
        x_acestep_launch_secret: str | None = Header(default=None),
    ) -> dict[str, object]:
        """Return Python-side diagnostics for the Tauri diagnostics report."""
        authenticate(x_acestep_launch_secret)
        if diagnostics_provider is not None:
            return diagnostics_provider()
        return {"error": "no diagnostics provider registered"}

    app.include_router(router)
