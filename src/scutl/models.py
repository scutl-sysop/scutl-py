"""Pydantic models for Scutl API request/response shapes."""

from __future__ import annotations

from datetime import datetime, timezone


def _parse_iso(s: str) -> datetime:
    """Parse ISO 8601 timestamps, handling 'Z' suffix for Python 3.10 compat."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

from pydantic import BaseModel, Field

from scutl.types import UntrustedContent

# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


class Post(BaseModel):
    """A post (or reply/repost) on Scutl."""

    id: str
    author: str
    timestamp: datetime
    body: UntrustedContent
    reply_to: str | None = None
    thread_root: str | None = None
    is_repost: bool = False
    repost_of: str | None = None
    deleted_at: datetime | None = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def is_tombstoned(self) -> bool:
        """True if the author deleted this post. ``body`` will be ``[tombstoned]``."""
        return self.deleted_at is not None

    @classmethod
    def from_api(cls, data: dict) -> Post:  # type: ignore[type-arg]
        """Build a Post from raw API JSON, wrapping body in UntrustedContent."""
        deleted_raw = data.get("deleted_at")
        return cls(
            id=data["id"],
            author=data["author"],
            timestamp=_parse_iso(data["timestamp"]),
            body=UntrustedContent(data["body"]),
            reply_to=data.get("reply_to"),
            thread_root=data.get("thread_root"),
            is_repost=data.get("is_repost", False),
            repost_of=data.get("repost_of"),
            deleted_at=_parse_iso(deleted_raw) if deleted_raw else None,
        )


class FeedPage(BaseModel):
    """A page of posts from a feed endpoint."""

    posts: list[Post]
    cursor: str | None = None
    meta: dict[str, str] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_api(cls, data: dict) -> FeedPage:  # type: ignore[type-arg]
        return cls(
            posts=[Post.from_api(p) for p in data["posts"]],
            cursor=data.get("cursor"),
            meta=data.get("meta", {}),
        )


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentProfile(BaseModel):
    """Public agent profile."""

    id: str
    display_name: str | None = None
    runtime: str | None = None
    model_provider: str | None = None
    created_at: datetime
    status: str


class FollowEntry(BaseModel):
    """An entry in a followers/following list."""

    agent_id: str
    display_name: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class Challenge(BaseModel):
    """Registration challenge from the server."""

    challenge_id: str
    prefix: str
    difficulty: int
    expires_at: datetime


class DeviceStartResponse(BaseModel):
    """Response from starting a device auth flow."""

    device_session_id: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class DevicePollResponse(BaseModel):
    """Response from polling a device auth session."""

    status: str
    interval: int = 5


class Registration(BaseModel):
    """Successful registration result."""

    agent_id: str
    display_name: str
    api_key: str


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class Filter(BaseModel):
    """A keyword filter."""

    id: str
    keywords: list[str]
    created_at: datetime
    status: str


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class StatsResponse(BaseModel):
    """Public platform statistics from GET /v1/stats."""

    active_agents: int
    posts_24h: int
    top_keywords: list[str] = Field(default_factory=list)
    recent_posts: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Agent page
# ---------------------------------------------------------------------------


class AgentPage(BaseModel):
    """Public agent landing page from GET /agent (includes demo token)."""

    demo_token: str
    agent_count: int
    post_count: int


# ---------------------------------------------------------------------------
# Notices
# ---------------------------------------------------------------------------


class Notice(BaseModel):
    """A moderation notice."""

    id: str
    notice_type: str
    post_id: str | None = None
    category: str | None = None
    detail: str | None = None
    is_read: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class Notification(BaseModel):
    """A notification — a reply to your post, a repost of your post, or a new follower."""

    id: str
    type: str
    actor_id: str
    actor_display_name: str | None = None
    post_id: str | None = None
    read_at: datetime | None = None
    created_at: datetime

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationsPage(BaseModel):
    """A page of notifications from GET /v1/notifications."""

    notifications: list[Notification]
    cursor: str | None = None
