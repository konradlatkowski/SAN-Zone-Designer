"""Log viewing endpoints (admin only)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from ..audit import AUDIT_LOG_FILE, audit_log
from ..auth import get_current_user, require_admin
from ..dependencies import DATABASE_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])

LOGS_DIR = DATABASE_DIR / "logs"
APP_LOG_FILE = LOGS_DIR / "san_zone_designer.log"


def _tail_lines(filepath: Path, max_lines: int = 500) -> list[str]:
    """Read the last N lines from a file efficiently."""
    if not filepath.exists():
        return []
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        lines = text.strip().splitlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _parse_audit_line(line: str) -> dict | None:
    """Parse a single JSON-lines audit entry."""
    try:
        return json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None


@router.get("/audit")
async def get_audit_logs(
    limit: int = Query(200, ge=1, le=2000),
    actor: str = Query("", description="Filter by actor username"),
    event_type: str = Query("", description="Filter by event_type prefix, e.g. 'auth' or 'config'"),
    project: str = Query("", description="Filter by project name"),
    outcome: str = Query("", description="Filter by outcome: success or failure"),
    user: dict = Depends(require_admin),
):
    """Return parsed audit log entries (newest first). Admin only."""
    audit_log("audit.viewed", user)

    raw_lines = _tail_lines(AUDIT_LOG_FILE, max_lines=2000)
    entries: list[dict] = []

    for line in reversed(raw_lines):
        entry = _parse_audit_line(line)
        if entry is None:
            continue

        # Apply filters
        if actor and entry.get("actor", "") != actor:
            continue
        if event_type and not entry.get("event_type", "").startswith(event_type):
            continue
        if project and entry.get("project", "") != project:
            continue
        if outcome and entry.get("outcome", "") != outcome:
            continue

        entries.append(entry)
        if len(entries) >= limit:
            break

    return {"entries": entries, "total": len(entries)}


@router.get("/app")
async def get_app_logs(
    limit: int = Query(200, ge=1, le=2000),
    level: str = Query("", description="Filter by log level: INFO, WARNING, ERROR"),
    user: dict = Depends(require_admin),
):
    """Return application log lines (newest first). Admin only."""
    raw_lines = _tail_lines(APP_LOG_FILE, max_lines=2000)
    entries: list[dict] = []

    for line in reversed(raw_lines):
        # Parse format: "2026-02-21 16:35:18 INFO     logger — message"
        parsed = _parse_app_log_line(line)
        if parsed is None:
            continue

        if level and parsed.get("level", "") != level.upper():
            continue

        entries.append(parsed)
        if len(entries) >= limit:
            break

    return {"entries": entries, "total": len(entries)}


def _parse_app_log_line(line: str) -> dict | None:
    """Parse a standard application log line into a dict."""
    # Format: "2026-02-21 16:35:18 INFO     san_zone_designer.web.auth — Session created..."
    try:
        # timestamp = first 19 chars
        if len(line) < 20:
            return None
        timestamp = line[:19]
        rest = line[20:].strip()

        # level is next word
        parts = rest.split(None, 2)
        if len(parts) < 2:
            return None

        level_str = parts[0]
        remainder = parts[1] if len(parts) == 2 else parts[1]

        # Split on " — " to separate logger from message
        if " — " in rest:
            after_level = rest[len(level_str):].strip()
            logger_msg = after_level.split(" — ", 1)
            logger_name = logger_msg[0].strip()
            message = logger_msg[1].strip() if len(logger_msg) > 1 else ""
        else:
            logger_name = ""
            message = rest[len(level_str):].strip()

        return {
            "timestamp": timestamp,
            "level": level_str,
            "logger": logger_name,
            "message": message,
        }
    except Exception:
        return None


@router.get("/actors")
async def get_actors(user: dict = Depends(require_admin)):
    """Return list of unique actors found in the audit log."""
    raw_lines = _tail_lines(AUDIT_LOG_FILE, max_lines=5000)
    actors: set[str] = set()
    for line in raw_lines:
        entry = _parse_audit_line(line)
        if entry and entry.get("actor"):
            actors.add(entry["actor"])
    return {"actors": sorted(actors)}


@router.get("/event-types")
async def get_event_types(user: dict = Depends(require_admin)):
    """Return list of unique event type prefixes found in audit log."""
    raw_lines = _tail_lines(AUDIT_LOG_FILE, max_lines=5000)
    types: set[str] = set()
    for line in raw_lines:
        entry = _parse_audit_line(line)
        if entry and entry.get("event_type"):
            # Return the prefix (first dot-segment)
            types.add(entry["event_type"].split(".")[0])
    return {"event_types": sorted(types)}
