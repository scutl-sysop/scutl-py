"""Scutl SDK exceptions."""

from __future__ import annotations


class ScutlError(Exception):
    """Base exception for all Scutl SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
        self, message: str, retry_after: float | None = None, status_code: int = 429
    ) -> None:
        super().__init__(message, status_code)
        self.retry_after = retry_after


class ValidationError(ScutlError):
    """Raised on 422 responses."""


class ChallengeExpiredError(ScutlError):
    """Raised on 410 responses (challenge or verification expired)."""
