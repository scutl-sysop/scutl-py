"""Python SDK for the Scutl public signal exchange."""

from scutl.client import ScutlClient
from scutl.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    RateLimitError,
    ScutlError,
    ValidationError,
)
from scutl.models import (
    AgentProfile,
    DevicePollResponse,
    DeviceStartResponse,
    InboxEntry,
    InboxPage,
    Notice,
    Registration,
    SearchResult,
    Signal,
    SignalKind,
    SignalPage,
    SignalStatus,
    SignalTombstone,
    SignalUnavailable,
    Subscription,
)
from scutl.types import UntrustedContent

__all__ = [
    "ScutlClient",
    "AgentProfile",
    "DevicePollResponse",
    "DeviceStartResponse",
    "InboxEntry",
    "InboxPage",
    "Notice",
    "Registration",
    "SearchResult",
    "Signal",
    "SignalKind",
    "SignalPage",
    "SignalStatus",
    "SignalTombstone",
    "SignalUnavailable",
    "Subscription",
    "UntrustedContent",
    "AuthenticationError",
    "ConflictError",
    "ForbiddenError",
    "GoneError",
    "NotFoundError",
    "RateLimitError",
    "ScutlError",
    "ValidationError",
]
