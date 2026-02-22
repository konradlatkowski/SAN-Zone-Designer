"""Structured audit logging for SAN Zone Designer.

Writes JSON-lines to database/logs/audit.log (separate from application log).
Each line is a self-contained JSON object with: timestamp, event_type, actor,
actor_role, project, detail, outcome.

Usage:
    from .audit import audit_log
    audit_log("config.generated", user, project="DC_Krakow",
              detail={"zones": 48, "vendor": "cisco"})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "database" / "logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "audit.log"

_audit_logger: logging.Logger | None = None


def _get_audit_logger() -> logging.Logger:
    """Lazy-init a dedicated audit logger writing JSON lines."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    _audit_logger = logging.getLogger("san_zone_designer.audit")
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False  # don't duplicate to root/console

    handler = logging.handlers.RotatingFileHandler(
        AUDIT_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(handler)

    return _audit_logger


def audit_log(
    event_type: str,
    user: dict | None = None,
    *,
    project: str = "",
    detail: dict | None = None,
    outcome: str = "success",
) -> None:
    """Write a structured audit entry.

    Args:
        event_type: Dot-namespaced event, e.g. "auth.login", "config.generated".
        user: The current user dict (from get_current_user), or None for system events.
        project: Project name if the action is project-scoped.
        detail: Arbitrary extra data dict (kept shallow).
        outcome: "success" or "failure".
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": user["username"] if user else "system",
        "actor_role": user.get("role", "") if user else "system",
        "project": project,
        "detail": detail or {},
        "outcome": outcome,
    }
    _get_audit_logger().info(json.dumps(entry, ensure_ascii=False))
