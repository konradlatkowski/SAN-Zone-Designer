"""FastAPI application for SAN Zone Designer web interface."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .. import __version__
from .auth import SESSION_STORE, _cleanup_expired, SESSION_TTL, ensure_default_admin
from .logging_config import setup_logging
from .routers import auth, config, diff, files, generate, logs, migrate

setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

_AUTH_WHITELIST = {"/api/auth/login", "/api/version"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in _AUTH_WHITELIST:
            token = request.cookies.get("session_token")
            if not token:
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            _cleanup_expired()
            session = SESSION_STORE.get(token)
            if not session:
                return JSONResponse(status_code=401, content={"detail": "Session expired"})
            # Sliding window refresh
            session["expires"] = time.time() + SESSION_TTL
        return await call_next(request)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    logger.info("Starting SAN Zone Designer v%s", __version__)
    ensure_default_admin()

    application = FastAPI(
        title="SAN Zone Designer",
        version=__version__,
        description="Web interface for SAN Zone Designer",
    )

    application.add_middleware(AuthMiddleware)

    application.include_router(auth.router)
    application.include_router(files.router)
    application.include_router(generate.router)
    application.include_router(migrate.router)
    application.include_router(diff.router)
    application.include_router(config.router)
    application.include_router(logs.router)

    @application.get("/api/version")
    async def get_version():
        return {"version": __version__}

    application.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return application


app = create_app()
