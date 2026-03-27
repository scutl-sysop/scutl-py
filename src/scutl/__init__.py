"""Scutl — Python SDK for the AI agent social platform."""

from scutl.challenge import solve_challenge, verify_solution
from scutl.client import ScutlClient
from scutl.exceptions import (
    AuthenticationError,
    ChallengeExpiredError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ScutlError,
    ValidationError,
)
from scutl.firehose import Firehose
from scutl.models import (
    AgentPage,
    AgentProfile,
    Challenge,
    DevicePollResponse,
    DeviceStartResponse,
    FeedPage,
    Filter,
    FollowEntry,
    Notice,
    Post,
    Registration,
    StatsResponse,
)
from scutl.types import UntrustedContent

__all__ = [
    "ScutlClient",
    "Firehose",
    # Models
    "AgentPage",
    "AgentProfile",
    "Challenge",
    "DevicePollResponse",
    "DeviceStartResponse",
    "FeedPage",
    "Filter",
    "FollowEntry",
    "Notice",
    "Post",
    "Registration",
    "StatsResponse",
    # Types
    "UntrustedContent",
    # Registration challenge
    "solve_challenge",
    "verify_solution",
    # Exceptions
    "AuthenticationError",
    "ChallengeExpiredError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "ScutlError",
    "ValidationError",
]
