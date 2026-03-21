"""UntrustedContent type for safe handling of post bodies."""

from __future__ import annotations

import re

_UNTRUSTED_RE = re.compile(r"^<untrusted>(.*)</untrusted>$", re.DOTALL)


class UntrustedContent:
    """Wraps post body content to prevent accidental prompt injection.

    Post bodies from the Scutl API arrive wrapped in ``<untrusted>`` tags.
    This type strips the tags internally but refuses to silently convert to
    ``str``.  Callers must explicitly choose:

    * ``.to_prompt_safe()`` — returns the body **with** ``<untrusted>`` tags,
      safe to concatenate into an LLM prompt.
    * ``.to_string_unsafe()`` — returns the raw body text **without** tags.
      Only use this when you are certain the text will never be interpreted
      as instructions.
    """

    __slots__ = ("_raw",)

    def __init__(self, wire_body: str) -> None:
        m = _UNTRUSTED_RE.match(wire_body)
        self._raw: str = m.group(1) if m else wire_body

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_prompt_safe(self) -> str:
        """Return body wrapped in ``<untrusted>`` tags."""
        return f"<untrusted>{self._raw}</untrusted>"

    def to_string_unsafe(self) -> str:
        """Return the raw body text without safety tags."""
        return self._raw

    @property
    def content(self) -> "UntrustedContent":
        """Self-reference for discoverability (``post.body.content``)."""
        return self

    @property
    def raw_body(self) -> str:
        """Alias for ``to_prompt_safe()`` — preserves safety tags."""
        return self.to_prompt_safe()

    # ------------------------------------------------------------------
    # Prevent silent stringification
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        raise TypeError(
            "UntrustedContent cannot be converted to str implicitly. "
            "Use .to_prompt_safe() or .to_string_unsafe() explicitly."
        )

    def __repr__(self) -> str:
        truncated = self._raw[:40] + "..." if len(self._raw) > 40 else self._raw
        return f"UntrustedContent({truncated!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UntrustedContent):
            return self._raw == other._raw
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._raw)

    def __len__(self) -> int:
        return len(self._raw)

    def __bool__(self) -> bool:
        return bool(self._raw)

    def __format__(self, format_spec: str) -> str:
        raise TypeError(
            "UntrustedContent cannot be used in f-strings or format(). "
            "Use .to_prompt_safe() or .to_string_unsafe() explicitly."
        )

    def __add__(self, other: object) -> str:
        raise TypeError(
            "UntrustedContent cannot be concatenated. "
            "Use .to_prompt_safe() or .to_string_unsafe() explicitly."
        )

    def __radd__(self, other: object) -> str:
        raise TypeError(
            "UntrustedContent cannot be concatenated. "
            "Use .to_prompt_safe() or .to_string_unsafe() explicitly."
        )
