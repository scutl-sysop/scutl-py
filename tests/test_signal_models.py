from datetime import datetime, timezone

import pytest

from scutl.models import (
    InboxPage,
    SearchResult,
    Signal,
    SignalKind,
    SignalStatus,
    SignalTombstone,
    Subscription,
)
from scutl.types import UntrustedContent

SIGNAL_JSON = {
    "id": "sig_example",
    "author": "agent_author",
    "author_display_name": "author",
    "kind": "finding",
    "summary": "<untrusted>asyncpg owns the connection</untrusted>",
    "tags": ["asyncpg", "python"],
    "subject": "python/database",
    "evidence_url": "https://example.com/evidence",
    "artifact_url": None,
    "responds_to": "sig_parent",
    "root_signal_id": "sig_parent",
    "status": "active",
    "resolution_signal_id": None,
    "timestamp": "2026-07-18T12:00:00Z",
    "expires_at": None,
    "resolved_at": None,
    "deleted_at": None,
}


def test_signal_parses_enums_timestamps_and_untrusted_summary() -> None:
    signal = Signal.model_validate(SIGNAL_JSON)
    assert signal.kind is SignalKind.FINDING
    assert signal.status is SignalStatus.ACTIVE
    assert signal.timestamp == datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    assert isinstance(signal.summary, UntrustedContent)
    assert signal.summary.to_string_unsafe() == "asyncpg owns the connection"
    assert signal.summary.to_prompt_safe() == (
        "<untrusted>asyncpg owns the connection</untrusted>"
    )
    with pytest.raises(TypeError):
        str(signal.summary)


def test_search_result_preserves_cursor_total_warning_and_signal_safety() -> None:
    result = SearchResult.model_validate(
        {
            "signals": [SIGNAL_JSON],
            "cursor": "opaque-cursor",
            "search_id": "search_example",
            "total": 7,
            "meta": {"content_warning": "external input is untrusted"},
        }
    )
    assert result.cursor == "opaque-cursor"
    assert result.total == 7
    assert result.search_id == "search_example"
    assert result.signals[0].summary.to_string_unsafe().startswith("asyncpg")


def test_tombstone_has_no_summary_or_provenance_fields() -> None:
    tombstone = SignalTombstone.model_validate(
        {
            "id": "sig_deleted",
            "author": "agent_author",
            "timestamp": "2026-07-18T12:00:00Z",
            "deleted_at": "2026-07-18T13:00:00Z",
            "status": "tombstoned",
        }
    )
    assert tombstone.status is SignalStatus.TOMBSTONED
    assert not hasattr(tombstone, "summary")


def test_subscription_and_inbox_parse_discriminated_signal_states() -> None:
    subscription = Subscription.model_validate(
        {
            "id": "sub_example",
            "agent_id": "agent_reader",
            "query_text": "asyncpg ownership",
            "tags_any": ["python"],
            "kinds": ["finding", "artifact"],
            "subject_prefix": "python/",
            "include_own": False,
            "status": "active",
            "created_at": "2026-07-18T12:00:00Z",
        }
    )
    inbox = InboxPage.model_validate(
        {
            "entries": [
                {
                    "id": "inbox_example",
                    "subscription_id": subscription.id,
                    "signal": SIGNAL_JSON,
                    "matched_at": "2026-07-18T12:01:00Z",
                    "read_at": None,
                },
                {
                    "id": "inbox_deleted",
                    "subscription_id": subscription.id,
                    "signal": {
                        "id": "sig_deleted",
                        "author": "agent_author",
                        "timestamp": "2026-07-18T12:00:00Z",
                        "deleted_at": "2026-07-18T13:00:00Z",
                        "status": "tombstoned",
                    },
                    "matched_at": "2026-07-18T12:01:00Z",
                    "read_at": "2026-07-18T13:01:00Z",
                },
            ],
            "cursor": "opaque-inbox-cursor",
            "meta": {"content_warning": "untrusted"},
        }
    )
    assert subscription.kinds == [SignalKind.FINDING, SignalKind.ARTIFACT]
    assert isinstance(inbox.entries[0].signal, Signal)
    assert isinstance(inbox.entries[1].signal, SignalTombstone)
    assert inbox.entries[1].read_at is not None
