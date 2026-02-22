"""Pydantic request/response models for the web API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    initiators_path: str
    targets_path: str
    vendor: str = "cisco"
    mode: str = "single"
    order: str = "ti"
    separator: str = "two"
    vsan: int = 0
    vsan_name: str = ""
    iface_range: str = "1-32"
    zoneset_name: str = ""
    fabric_filter: str = ""
    rollback: bool = False


class ExpandRequest(GenerateRequest):
    selected_pairs: list[dict] = Field(default_factory=list)


class MigrateRequest(BaseModel):
    input_path: str
    output_project: str
    output_filename: str
    file_type: str = "auto"


class DiffRequest(GenerateRequest):
    existing_path: str = ""


class ProjectCreateRequest(BaseModel):
    name: str


class ZoneEntry(BaseModel):
    name: str
    initiator_alias: str
    initiator_wwpn: str
    target_aliases: list[str]
    target_wwpns: list[str]


class GenerateResponse(BaseModel):
    config: str
    summary: dict
    csv: str
    rollback_cfg: str = ""
    zones: list[ZoneEntry]
    saved_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    initiators: list[dict]
    targets: list[dict]
    zones: list[ZoneEntry]
    summary: dict
    warnings: list[str] = Field(default_factory=list)


class MigratePreviewResponse(BaseModel):
    yaml_content: str
    entry_count: int
    file_type: str


class DiffResponse(BaseModel):
    added: list[dict]
    removed: list[dict]
    unchanged: list[dict]
    modified: list[dict]
    summary: dict
    saved_files: list[str] = Field(default_factory=list)


class FileInfo(BaseModel):
    name: str
    type: str
    size: int


class ProjectInfo(BaseModel):
    name: str
    files: list[FileInfo]


class FileListResponse(BaseModel):
    projects: list[ProjectInfo]


class FileContentResponse(BaseModel):
    content: str
    entries: list[dict]
    file_type: str
    warnings: list[str] = Field(default_factory=list)


# ── Auth models ──

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    role: str
    projects: list[str] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    projects: list[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    projects: list[str] = Field(default_factory=list)
