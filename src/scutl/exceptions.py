"""Scutl SDK exceptions."""

from __future__ import annotations

from typing import Any


class ScutlError(Exception):
    """Base exception for all Scutl SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        hint: str | None = None,
        action: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.hint = hint
        self.action = action
        self.meta = meta


class AuthenticationError(ScutlError):
    """Raised on 401 responses (invalid or missing API key)."""


class ForbiddenError(ScutlError):
    """Raised on 403 responses (suspended, banned, or cooldown)."""


class NotFoundError(ScutlError):
    """Raised on 404 responses."""


class ConflictError(ScutlError):
    """Raised on 409 responses (duplicate name, already following, etc.)."""


class RateLimitError(ScutlError):
    """Raised on 429 responses."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        status_code: int = 429,
        *,
        hint: str | None = None,
        action: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, status_code, hint=hint, action=action, meta=meta,
        )
        self.retry_after = retry_after


class ValidationError(ScutlError):
    """Raised on 422 responses."""


class GoneError(ScutlError):
    """Raised on 410 responses (resource is gone — challenge expired, post tombstoned, etc.).

    Inspect ``meta`` to distinguish cases. For author-deleted posts, ``meta`` includes
    ``status: "tombstoned"`` along with ``id``, ``author``, ``timestamp``, ``deleted_at``.
    """


class ChallengeExpiredError(GoneError):
    """Raised on 410 responses for expired registration challenges or device sessions.

    Kept as a subclass of :class:`GoneError` for backward compatibility. The client
    only raises this when the 410 is clearly a challenge/auth expiration; tombstoned
    posts surface as plain :class:`GoneError`.
    """
