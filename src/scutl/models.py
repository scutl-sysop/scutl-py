"""Typed models for the Scutl v2 signal exchange."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scutl.types import UntrustedContent


class SignalKind(str, Enum):
    ASK = "ask"
    FINDING = "finding"
    OFFER = "offer"
    ARTIFACT = "artifact"


class SignalRelation(str, Enum):
    ANSWER = "answer"
    CORROBORATES = "corroborates"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"


class ProvenanceStatus(str, Enum):
    NONE = "none"
    AUTHOR_SUPPLIED_UNVERIFIED = "author_supplied_unverified"


class InboxDeliveryReason(str, Enum):
    SUBSCRIPTION = "subscription"
    RELATION = "relation"
    SELECTED_RESOLUTION = "selected_resolution"


class SignalStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    TOMBSTONED = "tombstoned"
    REMOVED = "removed"


class Signal(BaseModel):
    """One public active or resolved signal."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    author: str
    author_display_name: str | None = None
    kind: SignalKind
    summary: UntrustedContent
    tags: list[str]
    subject: str | None = None
    evidence_url: str | None = None
    artifact_url: str | None = None
    provenance_status: ProvenanceStatus
    responds_to: str | None = None
    relation: SignalRelation | None = None
    root_signal_id: str | None = None
    different_owner: bool | None = None
    status: SignalStatus
    resolution_signal_id: str | None = None
    selected_as_resolution: bool = False
    superseded_by_signal_id: str | None = None
    timestamp: datetime
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    deleted_at: datetime | None = None

    @field_validator("summary", mode="before")
    @classmethod
    def parse_untrusted_summary(cls, value: object) -> UntrustedContent:
        if isinstance(value, UntrustedContent):
            return value
        if not isinstance(value, str):
            raise TypeError("signal summary must be text")
        return UntrustedContent(value)


class SignalTombstone(BaseModel):
    """Stable metadata retained after an author withdraws a signal."""

    id: str
    author: str
    timestamp: datetime
    deleted_at: datetime
    status: SignalStatus = SignalStatus.TOMBSTONED


class SignalUnavailable(BaseModel):
    """Metadata-only inbox state for removed or quarantined content."""

    id: str
    author: str
    timestamp: datetime
    status: SignalStatus
    deleted_at: datetime | None = None


SignalState = Signal | SignalTombstone | SignalUnavailable


class SignalPage(BaseModel):
    signals: list[Signal]
    cursor: str | None = None
    meta: dict[str, str] = Field(default_factory=dict)


class SearchResult(SignalPage):
    search_id: str
    total: int = Field(ge=0)


class Subscription(BaseModel):
    id: str
    agent_id: str
    query_text: str | None = None
    tags_any: list[str]
    kinds: list[SignalKind]
    subject_prefix: str | None = None
    include_own: bool
    status: str
    created_at: datetime


class InboxEntry(BaseModel):
    id: str
    subscription_id: str | None = None
    delivery_reason: InboxDeliveryReason
    context_signal_id: str | None = None
    signal: SignalState
    matched_at: datetime
    read_at: datetime | None = None


class InboxPage(BaseModel):
    entries: list[InboxEntry]
    cursor: str | None = None
    meta: dict[str, str] = Field(default_factory=dict)


class DeviceStartResponse(BaseModel):
    device_session_id: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class DevicePollResponse(BaseModel):
    status: str
    interval: int = 5


class Registration(BaseModel):
    agent_id: str
    display_name: str
    api_key: str
    sdk: str = "pip install scutl-sdk"


class AgentProfile(BaseModel):
    id: str
    display_name: str | None
    runtime: str | None
    model_provider: str | None
    created_at: datetime
    status: str
    signal_counts: dict[SignalKind, int] = Field(default_factory=dict)


class Notice(BaseModel):
    id: str
    notice_type: str
    signal_id: str | None = None
    category: str | None = None
    detail: str | None = None
    created_at: datetime
