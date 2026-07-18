"""Tests for authenticated desktop lifecycle routes."""

import asyncio
import unittest

from fastapi import FastAPI, HTTPException

from acestep.desktop_routes import register_desktop_routes


class DesktopRoutesTests(unittest.TestCase):
    """Verify desktop lifecycle authentication and distinct readiness state."""

    def _endpoint(self, path: str, ready: bool):
        """Return a registered lifecycle endpoint for direct unit testing."""
        app = FastAPI()
        register_desktop_routes(app, "secret", lambda: ready)
        return next(route.endpoint for route in app.routes if route.path == path)

    def test_health_requires_launch_secret(self) -> None:
        """Desktop health must not be accessible without the launch secret."""
        endpoint = self._endpoint("/desktop/health", ready=True)
        with self.assertRaises(HTTPException) as context:
            asyncio.run(endpoint(None))
        self.assertEqual(401, context.exception.status_code)
        self.assertEqual({"status": "ok"}, asyncio.run(endpoint("secret")))

    def test_readiness_reports_starting_and_ready(self) -> None:
        """Readiness should remain distinct from process health."""
        starting = asyncio.run(self._endpoint("/desktop/ready", ready=False)("secret"))
        ready = asyncio.run(self._endpoint("/desktop/ready", ready=True)("secret"))
        self.assertEqual({"status": "starting", "ready": False}, starting)
        self.assertEqual({"status": "ready", "ready": True}, ready)

    def test_empty_launch_secret_is_rejected(self) -> None:
        """Route registration must reject an unauthenticated configuration."""
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            register_desktop_routes(FastAPI(), "", lambda: True)


if __name__ == "__main__":
    unittest.main()
