"""Authentication API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

logger = logging.getLogger(__name__)

from ..auth import (
    SESSION_STORE,
    create_session,
    get_current_user,
    hash_password,
    load_users,
    require_admin,
    save_users,
    verify_password,
)
from ..audit import audit_log
from ..schemas import LoginRequest, PasswordChangeRequest, UserCreateRequest, UserInfo, UserUpdateRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response):
    users = load_users()
    user = next((u for u in users if u["username"] == body.username), None)
    if not user or not verify_password(body.password, user["password_hash"]):
        logger.warning("Failed login attempt for username '%s'", body.username)
        audit_log("auth.login_failed", detail={"username": body.username}, outcome="failure")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    projects = user.get("projects", [])
    token = create_session(user["username"], user["role"], projects)
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=is_https,
        samesite="strict" if is_https else "lax",
        path="/",
    )
    logger.info("User '%s' logged in (role=%s)", user["username"], user["role"])
    audit_log("auth.login", {"username": user["username"], "role": user["role"]})
    return {"username": user["username"], "role": user["role"], "projects": projects}


@router.post("/logout")
def logout(response: Response, user: dict = Depends(get_current_user)):
    audit_log("auth.logout", user)
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return UserInfo(username=user["username"], role=user["role"], projects=user.get("projects", []))


@router.get("/users", response_model=list[UserInfo])
def list_users(user: dict = Depends(require_admin)):
    users = load_users()
    return [UserInfo(username=u["username"], role=u["role"], projects=u.get("projects", [])) for u in users]


@router.post("/users", response_model=UserInfo, status_code=201)
def create_user(body: UserCreateRequest, user: dict = Depends(require_admin)):
    users = load_users()
    if any(u["username"] == body.username for u in users):
        raise HTTPException(status_code=409, detail=f"User '{body.username}' already exists")
    new_user = {
        "username": body.username,
        "role": body.role,
        "password_hash": hash_password(body.password),
    }
    if body.role != "admin":
        new_user["projects"] = body.projects
    users.append(new_user)
    save_users(users)
    logger.info("Admin '%s' created user '%s' (role=%s)", user["username"], body.username, body.role)
    audit_log("user.created", user, detail={"target_user": body.username, "role": body.role, "projects": body.projects})
    return UserInfo(username=body.username, role=body.role, projects=body.projects if body.role != "admin" else [])


@router.put("/users/{username}")
def update_user(username: str, body: UserUpdateRequest, user: dict = Depends(require_admin)):
    users = load_users()
    target = next((u for u in users if u["username"] == username), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    if target["role"] == "admin":
        raise HTTPException(status_code=400, detail="Cannot set projects for admin users")
    target["projects"] = body.projects
    save_users(users)
    # Update existing sessions for this user
    for session in SESSION_STORE.values():
        if session["username"] == username:
            session["projects"] = body.projects
    audit_log("user.projects_updated", user, detail={"target_user": username, "projects": body.projects})
    return UserInfo(username=username, role=target["role"], projects=body.projects)


@router.delete("/users/{username}")
def delete_user(username: str, user: dict = Depends(require_admin)):
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    users = load_users()
    new_users = [u for u in users if u["username"] != username]
    if len(new_users) == len(users):
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    save_users(new_users)
    # Remove any active sessions for deleted user
    to_remove = [t for t, s in SESSION_STORE.items() if s["username"] == username]
    for t in to_remove:
        del SESSION_STORE[t]
    logger.info("Admin '%s' deleted user '%s' (invalidated %d sessions)", user["username"], username, len(to_remove))
    audit_log("user.deleted", user, detail={"target_user": username, "sessions_invalidated": len(to_remove)})
    return {"ok": True}


@router.put("/password")
def change_password(body: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    """Allow any authenticated user to change their own password."""
    if len(body.new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    users = load_users()
    target = next((u for u in users if u["username"] == user["username"]), None)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, target["password_hash"]):
        audit_log("auth.password_change_failed", user, outcome="failure")
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    target["password_hash"] = hash_password(body.new_password)
    save_users(users)
    logger.info("User '%s' changed their password", user["username"])
    audit_log("auth.password_changed", user)
    return {"ok": True, "message": "Password changed successfully"}
