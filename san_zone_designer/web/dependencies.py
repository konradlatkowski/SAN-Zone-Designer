"""Shared dependencies and helpers for the web interface."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

from ..generators import BrocadeGenerator, CiscoGenerator
from ..models import Configuration, NameOrder, Vendor, ZoneMode
from ..parser import load_initiators, load_targets

DATABASE_DIR = Path(__file__).resolve().parent.parent.parent / "database"
GENERATED_DIR = DATABASE_DIR / "_generated"
DELETED_DIR = DATABASE_DIR / "deleted"


def resolve_db_path(relative_path: str) -> Path:
    """Resolve a relative path inside DATABASE_DIR with path-traversal protection."""
    resolved = (DATABASE_DIR / relative_path).resolve()
    if not str(resolved).startswith(str(DATABASE_DIR.resolve())):
        logger.warning("Path traversal attempt blocked: %r", relative_path)
        raise HTTPException(status_code=400, detail="Invalid path: traversal detected")
    return resolved


def build_web_config(
    initiators_path: str,
    targets_path: str,
    vendor: str = "cisco",
    mode: str = "single",
    order: str = "ti",
    separator: str = "two",
    vsan: int = 0,
    vsan_name: str = "",
    iface_range: str = "1-32",
    zoneset_name: str = "",
    fabric_filter: str = "",
    rollback: bool = False,
) -> Configuration:
    """Build Configuration from web request parameters (mirrors cli._build_config)."""
    vendor_enum = Vendor(vendor)
    mode_enum = ZoneMode(mode)
    order_enum = NameOrder(order)

    sep = "__"
    if separator == "one":
        sep = "_"
    elif separator == "two":
        sep = "__"

    if vendor_enum == Vendor.cisco:
        effective_vsan_name = vsan_name or f"VSAN_{vsan}"
        effective_zoneset = zoneset_name or f"zoneset_vsan_{vsan}"
    else:
        effective_vsan_name = ""
        effective_zoneset = zoneset_name or "cfg"

    abs_init = resolve_db_path(initiators_path)
    abs_tgt = resolve_db_path(targets_path)

    if not abs_init.exists():
        raise HTTPException(status_code=404, detail=f"Initiators file not found: {initiators_path}")
    if not abs_tgt.exists():
        raise HTTPException(status_code=404, detail=f"Targets file not found: {targets_path}")

    inits = load_initiators(abs_init)
    tgts = load_targets(abs_tgt, mode=mode)

    if fabric_filter:
        inits = [h for h in inits if h.fabric.lower() == fabric_filter.lower()]
        tgts = [t for t in tgts if t.fabric.lower() == fabric_filter.lower()]
        if not inits and not tgts:
            raise HTTPException(status_code=400, detail=f"No initiators or targets found for fabric '{fabric_filter}'")

    if not inits:
        raise HTTPException(status_code=400, detail="No valid initiators found")
    if not tgts:
        raise HTTPException(status_code=400, detail="No valid targets found")

    return Configuration(
        vendor=vendor_enum,
        mode=mode_enum,
        order=order_enum,
        separator=sep,
        vsan=vsan,
        vsan_name=effective_vsan_name,
        iface_range=iface_range,
        zoneset_name=effective_zoneset,
        initiators=inits,
        targets=tgts,
        dry_run=False,
        rollback=rollback,
    )


def soft_delete_project(project_name: str) -> str:
    """Move a project directory to deleted/ with a timestamp suffix.

    Returns the relative path inside deleted/ where the project was archived,
    e.g. 'deleted/DC_Krakow_2026-02-21_14-30-00'.
    """
    DELETED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest_name = f"{project_name}_{ts}"
    dest = DELETED_DIR / dest_name
    # Avoid collision if two deletes happen in the same second
    counter = 1
    while dest.exists():
        dest = DELETED_DIR / f"{dest_name}_{counter}"
        counter += 1
    import shutil
    shutil.move(str(resolve_db_path(project_name)), str(dest))
    return f"deleted/{dest.name}"


def soft_delete_file(project: str, filename: str) -> str:
    """Move a single file to deleted/{project}/ with a timestamp suffix.

    filename may be a plain name ('file.cfg') or include a subdirectory
    prefix such as '_output/file.cfg'.  Returns the relative archived path
    inside DATABASE_DIR, e.g. 'deleted/MyProject/file_2026-02-21_14-30-00.cfg'.
    """
    DELETED_DIR.mkdir(parents=True, exist_ok=True)
    file_path = resolve_db_path(f"{project}/{filename}")

    stem = file_path.stem
    ext = file_path.suffix
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    dest_dir = DELETED_DIR / project
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"{stem}_{ts}{ext}"
    dest = dest_dir / dest_name
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{ts}_{counter}{ext}"
        counter += 1

    import shutil
    shutil.move(str(file_path), str(dest))
    return f"deleted/{project}/{dest.name}"


def get_generator(config: Configuration):
    """Return the appropriate generator for the vendor."""
    if config.vendor == Vendor.cisco:
        return CiscoGenerator(config)
    return BrocadeGenerator(config)


def autosave(action: str, content: str, extension: str = ".cfg", project: str = "") -> str:
    """Auto-save content to the project working directory with timestamped filename.

    Args:
        action: Action name (e.g. 'initial', 'expand', 'migrate', 'diff').
        content: Text content to save.
        extension: File extension (e.g. '.cfg', '.csv', '.yaml', '.txt').
        project: Project directory name. Falls back to _generated/ if empty.

    Returns:
        Relative path from DATABASE_DIR (e.g. 'MyProject/initial_2026-02-20_14-30-00.cfg').
    """
    if project:
        target_dir = resolve_db_path(f"{project}/_output")
    else:
        target_dir = GENERATED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{action}_{ts}{extension}"
    path = target_dir / filename
    # Avoid overwrite in same second
    counter = 1
    while path.exists():
        filename = f"{action}_{ts}_{counter}{extension}"
        path = target_dir / filename
        counter += 1
    path.write_text(content, encoding="utf-8")

    prefix = f"{project}/_output" if project else "_generated"
    return f"{prefix}/{filename}"
