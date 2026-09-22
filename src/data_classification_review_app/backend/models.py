from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from .. import __version__
from .._metadata import app_name


class VersionOut(BaseModel):
    version: str

    @classmethod
    def from_metadata(cls) -> "VersionOut":
        return cls(version=__version__)


class PrincipalSearchResult(BaseModel):
    id: str
    name: str
    kind: str
    initials: str
    accent: str
    email: Optional[str] = None
    members: Optional[int] = None


class PrincipalOut(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    kind: str
    initials: str
    accent: str
    team: Optional[str] = None
    members: Optional[int] = None
    is_admin: bool
    assignment_count: Optional[int] = None


class MeOut(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    initials: str
    accent: str
    team: Optional[str] = None
    is_admin: bool
    is_mock_mode: bool
    all_users: Optional[list[PrincipalOut]] = None


class ProposalOut(BaseModel):
    key: str
    catalog: str
    schema_name: str
    table: str
    column: str
    data_type: str
    table_key: str
    class_tag: str
    confidence: Optional[str] = None
    frequency: Optional[float] = None
    latest_detected_time: Optional[str] = None
    owner: str
    status: str = "pending"
    modified_tag: Optional[str] = None
    comment: Optional[str] = None
    reviewer: Optional[str] = None
    decided_at: Optional[str] = None
    user_added: bool = False
    applied_at: Optional[str] = None


class TableSummaryOut(BaseModel):
    key: str
    catalog: str
    schema: str
    table: str
    owner: str
    last_scan: str
    total_cols: int
    proposal_count: int
    pending: int
    approved: int
    rejected: int
    modified: int
    high_conf: int
    low_conf: int
    proposals: list[ProposalOut] = []


class ColumnDetailOut(BaseModel):
    catalog: str
    schema_name: str
    table: str
    column: str
    data_type: str
    table_key: str
    owner: str
    existing_tags: list[str] = []
    class_tag: Optional[str] = None
    confidence: Optional[str] = None
    frequency: Optional[float] = None
    column_description: Optional[str] = None


class ColumnsResponse(BaseModel):
    columns: list[ColumnDetailOut]
    table_description: Optional[str] = None
    table_tags: list[str] = []
    metadata_denied: bool = False
    table_tags_denied: bool = False
    column_tags_denied: bool = False


class ColumnSamplesOut(BaseModel):
    column: str
    samples: list[str] = []


class TableSamplesOut(BaseModel):
    columns: list[ColumnSamplesOut]
    denied: bool


class DecisionPatchIn(BaseModel):
    column_key: str
    status: str
    modified_tag: Optional[str] = None
    comment: Optional[str] = None
    user_added: bool = False
    class_tag: Optional[str] = None


class DecisionOut(BaseModel):
    id: Optional[str] = None
    column_key: str
    scan_ts: Optional[str] = None
    status: str
    modified_tag: Optional[str] = None
    comment: Optional[str] = None
    reviewer: str
    decided_at: str
    user_added: bool
    applied_at: Optional[str] = None
    catalog: Optional[str] = None
    schema_name: Optional[str] = None
    table: Optional[str] = None
    column: Optional[str] = None
    class_tag: Optional[str] = None


class StewardAssignmentOut(BaseModel):
    id: str
    principal: str
    principal_kind: str
    scope: str
    catalog: str
    schema_name: Optional[str] = None
    table_name: Optional[str] = None


class StewardAssignmentIn(BaseModel):
    principal: str
    principal_kind: str
    scope: str
    catalog: str
    schema_name: Optional[str] = None
    table_name: Optional[str] = None


class SaveDecisionsOut(BaseModel):
    saved: int


class ApplyTagsIn(BaseModel):
    column_keys: list[str]
    class_tags: dict[str, str] = {}  # column_key → class_tag, used as fallback when no modified_tag


class ApplyTagsOut(BaseModel):
    applied: int
    skipped: int
    errors: list[dict] = []


class PatchStewardIn(BaseModel):
    is_admin: bool


class PrincipalIn(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    kind: str
    initials: str
    accent: str
    members: Optional[int] = None


class TagConfigOut(BaseModel):
    key: str
    enabled: bool
    description: Optional[str] = None
    allowed_values: list[str] = []


class TagRefreshOut(BaseModel):
    added: int
    added_enabled: int
    added_disabled: int
    total: int


class TagPatchIn(BaseModel):
    enabled: bool
    force: bool = False


class TagPatchOut(BaseModel):
    key: str
    enabled: bool
    active_proposals: int
