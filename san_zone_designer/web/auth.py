"""Authentication core: secrets file, password hashing, session management."""

from __future__ import annotations

import json
import logging
import secrets
import time
import warnings
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, HTTPException, Request

from .dependencies import DATABASE_DIR

logger = logging.getLogger(__name__)

SECRETS_PATH = DATABASE_DIR / ".secrets.json"

SESSION_STORE: dict[str, dict[str, Any]] = {}
SESSION_TTL = 900  # 15 minutes


# ── Password hashing ──

def hash_password(plain: str) -> str:
    import bcrypt
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Secrets file ──

def load_users() -> list[dict]:
    if not SECRETS_PATH.exists():
        return []
    data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    return data.get("users", [])


def save_users(users: list[dict]) -> None:
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(json.dumps({"users": users}, indent=2), encoding="utf-8")


def ensure_default_admin() -> None:
    users = load_users()
    if users:
        return
    users.append({
        "username": "admin",
        "role": "admin",
        "password_hash": hash_password("admin"),
    })
    save_users(users)
    warnings.warn("Default admin account created (admin/admin). Change the password!", stacklevel=1)
    logger.warning("Default admin account created with default password — change it immediately!")


# ── Sessions ──

def create_session(username: str, role: str, projects: list[str] | None = None) -> str:
    token = secrets.token_hex(32)
    SESSION_STORE[token] = {
        "username": username,
        "role": role,
        "projects": projects or [],
        "expires": time.time() + SESSION_TTL,
    }
    logger.info("Session created for user '%s' (role=%s)", username, role)
    return token


def _cleanup_expired() -> None:
    now = time.time()
    expired = [t for t, s in SESSION_STORE.items() if s["expires"] < now]
    for t in expired:
        del SESSION_STORE[t]


def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    _cleanup_expired()
    session = SESSION_STORE.get(token)
    if not session:
        logger.warning("Invalid or expired session token from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=401, detail="Session expired")
    # Sliding window: refresh TTL
    session["expires"] = time.time() + SESSION_TTL
    return {"username": session["username"], "role": session["role"], "projects": session.get("projects", [])}


def check_project_access(user: dict, project: str) -> None:
    """Raise 403 if user does not have access to the given project. Admin always OK."""
    if user["role"] == "admin":
        return
    if project not in user.get("projects", []):
        raise HTTPException(status_code=403, detail=f"Access denied to project '{project}'")


def grant_project_access(username: str, project: str) -> None:
    """Add project to user's allowed projects in secrets file and all active sessions."""
    users = load_users()
    user_record = next((u for u in users if u["username"] == username), None)
    if user_record is None or user_record.get("role") == "admin":
        return
    if project not in user_record.get("projects", []):
        user_record.setdefault("projects", []).append(project)
        save_users(users)
        logger.info("Granted access to project '%s' for user '%s'", project, username)
    # Sync all active sessions for this user
    for session in SESSION_STORE.values():
        if session["username"] == username and project not in session.get("projects", []):
            session.setdefault("projects", []).append(project)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
