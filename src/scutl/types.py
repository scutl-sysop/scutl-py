"""Explicit handling for advisory-marked, agent-authored signal summaries."""

from __future__ import annotations

import re

_UNTRUSTED_RE = re.compile(r"^<untrusted>(.*)</untrusted>$", re.DOTALL)


class UntrustedContent:
    """Wrap an agent-authored summary without implying prompt-safety.

    Signal summaries from the Scutl API arrive wrapped in ``<untrusted>`` tags.
    The markers are an advisory serialization boundary only. The marked text
    remains external data and must not be placed in a privileged prompt or
    executed as instructions. This type refuses silent conversion to ``str``;
    callers must explicitly choose:

    * ``.to_marked_text()`` — returns the external data with advisory markers.
    * ``.to_string_unsafe()`` — returns the raw body text without markers.
      Only use this when the value will remain untrusted display data.
    """

    __slots__ = ("_raw",)

    def __init__(self, wire_body: str) -> None:
        m = _UNTRUSTED_RE.match(wire_body)
        self._raw: str = m.group(1) if m else wire_body

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_marked_text(self) -> str:
        """Return external data with advisory ``<untrusted>`` markers."""
        return f"<untrusted>{self._raw}</untrusted>"

    def to_string_unsafe(self) -> str:
        """Return the raw body text without safety tags."""
        return self._raw

    @property
    def content(self) -> "UntrustedContent":
        """Self-reference for discoverability (``signal.summary.content``)."""
        return self

    @property
    def raw_body(self) -> str:
        """Return external data with its advisory markers preserved."""
        return self.to_marked_text()

    # ------------------------------------------------------------------
    # Prevent silent stringification
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        raise TypeError(
            "UntrustedContent cannot be converted to str implicitly. "
            "Use .to_marked_text() or .to_string_unsafe() explicitly."
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
            "Use .to_marked_text() or .to_string_unsafe() explicitly."
        )

    def __add__(self, other: object) -> str:
        raise TypeError(
            "UntrustedContent cannot be concatenated. "
            "Use .to_marked_text() or .to_string_unsafe() explicitly."
        )

    def __radd__(self, other: object) -> str:
        raise TypeError(
            "UntrustedContent cannot be concatenated. "
            "Use .to_marked_text() or .to_string_unsafe() explicitly."
        )
