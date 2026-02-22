"""Web interface for SAN Zone Designer."""


def create_app():
    """Lazy import to avoid requiring fastapi at CLI import time."""
    from .app import create_app as _create_app

    return _create_app()


__all__ = ["create_app"]
