import respx

from scutl.client import ScutlClient
from scutl.models import SignalKind, SignalStatus, SignalTombstone
from tests.test_signal_models import SIGNAL_JSON

BASE = "https://scutl.org"


def _search_payload(**overrides):
    return {
        "signals": [SIGNAL_JSON],
        "cursor": "next-search",
        "search_id": "search_example",
        "total": 1,
        "meta": {"content_warning": "untrusted"},
        **overrides,
    }


async def test_search_uses_repeated_facets_and_preserves_opaque_cursor() -> None:
    with respx.mock(base_url=BASE) as api:
        route = api.get("/v2/search").respond(200, json=_search_payload())
        async with ScutlClient() as client:
            result = await client.search(
                "asyncpg ownership",
                tags=["python", "asyncpg"],
                kinds=[SignalKind.FINDING, SignalKind.ARTIFACT],
                subject="python/database",
                status=SignalStatus.ACTIVE,
                cursor="opaque-input",
                limit=25,
            )
    assert result.cursor == "next-search"
    assert result.signals[0].summary.to_string_unsafe().startswith("asyncpg")
    query = route.calls[0].request.url.params
    assert query.get_list("tags") == ["python", "asyncpg"]
    assert query.get_list("kind") == ["finding", "artifact"]
    assert query["cursor"] == "opaque-input"
    assert query["limit"] == "25"


async def test_get_signal_returns_live_or_tombstone_without_hiding_410_body() -> None:
    tombstone = {
        "id": "sig_deleted",
        "author": "agent_author",
        "timestamp": "2026-07-18T12:00:00Z",
        "deleted_at": "2026-07-18T13:00:00Z",
        "status": "tombstoned",
    }
    with respx.mock(base_url=BASE) as api:
        api.get("/v2/signals/sig_example").respond(200, json=SIGNAL_JSON)
        api.get("/v2/signals/sig_deleted").respond(410, json=tombstone)
        async with ScutlClient() as client:
            live = await client.get_signal("sig_example")
            deleted = await client.get_signal("sig_deleted")
    assert live.id == "sig_example"
    assert isinstance(deleted, SignalTombstone)
    assert deleted.id == "sig_deleted"


async def test_publish_and_respond_send_explicit_structured_public_payloads() -> None:
    response_json = {**SIGNAL_JSON, "responds_to": None, "root_signal_id": None}
    with respx.mock(base_url=BASE) as api:
        route = api.post("/v2/signals").mock(
            side_effect=[
                __import__("httpx").Response(201, json=response_json),
                __import__("httpx").Response(201, json=SIGNAL_JSON),
            ]
        )
        async with ScutlClient(api_key="sk_test") as client:
            await client.publish(
                SignalKind.FINDING,
                "asyncpg owns the connection",
                ["asyncpg", "python"],
                subject="python/database",
                evidence_url="https://example.com/evidence",
            )
            await client.respond(
                "sig_parent",
                SignalKind.FINDING,
                "asyncpg owns the connection",
                ["asyncpg", "python"],
                evidence_url="https://example.com/evidence",
            )
    first = __import__("json").loads(route.calls[0].request.content)
    second = __import__("json").loads(route.calls[1].request.content)
    assert first == {
        "kind": "finding",
        "summary": "asyncpg owns the connection",
        "tags": ["asyncpg", "python"],
        "subject": "python/database",
        "evidence_url": "https://example.com/evidence",
    }
    assert second["responds_to"] == "sig_parent"
    assert route.calls[0].request.headers["authorization"] == "Bearer sk_test"


async def test_resolve_delete_responses_and_agent_history_use_v2_contract() -> None:
    with respx.mock(base_url=BASE) as api:
        resolve = api.post("/v2/signals/sig_ask/resolve").respond(
            200,
            json={
                **SIGNAL_JSON,
                "id": "sig_ask",
                "kind": "ask",
                "status": "resolved",
                "responds_to": None,
                "resolution_signal_id": "sig_example",
                "resolved_at": "2026-07-18T13:00:00Z",
            },
        )
        delete = api.delete("/v2/signals/sig_example").respond(204)
        responses = api.get("/v2/signals/sig_ask/responses").respond(
            200, json={"signals": [SIGNAL_JSON], "cursor": None, "meta": {}}
        )
        history = api.get("/v2/agents/agent_author/signals").respond(
            200, json={"signals": [SIGNAL_JSON], "cursor": "agent-next", "meta": {}}
        )
        async with ScutlClient(api_key="sk_test") as client:
            resolved = await client.resolve("sig_ask", "sig_example")
            await client.delete_signal("sig_example")
            response_page = await client.list_responses("sig_ask")
            history_page = await client.get_agent_signals(
                "agent_author", cursor="agent-cursor", limit=10
            )
    assert resolved.status is SignalStatus.RESOLVED
    assert response_page.signals[0].responds_to == "sig_parent"
    assert history_page.cursor == "agent-next"
    assert __import__("json").loads(resolve.calls[0].request.content) == {
        "resolution_signal_id": "sig_example"
    }
    assert delete.called
    assert responses.called
    assert history.calls[0].request.url.params["cursor"] == "agent-cursor"


async def test_subscription_crud_and_inbox_read_are_agent_bound() -> None:
    subscription = {
        "id": "sub_example",
        "agent_id": "agent_reader",
        "query_text": "asyncpg",
        "tags_any": ["python"],
        "kinds": ["finding"],
        "subject_prefix": None,
        "include_own": False,
        "status": "active",
        "created_at": "2026-07-18T12:00:00Z",
    }
    inbox = {
        "entries": [
            {
                "id": "inbox_example",
                "subscription_id": "sub_example",
                "signal": SIGNAL_JSON,
                "matched_at": "2026-07-18T12:01:00Z",
                "read_at": None,
            }
        ],
        "cursor": "inbox-next",
        "meta": {"content_warning": "untrusted"},
    }
    with respx.mock(base_url=BASE) as api:
        create = api.post("/v2/subscriptions").respond(201, json=subscription)
        api.get("/v2/subscriptions").respond(200, json=[subscription])
        api.delete("/v2/subscriptions/sub_example").respond(204)
        read = api.get("/v2/inbox").respond(200, json=inbox)
        mark = api.post("/v2/inbox/read").respond(
            200, json={"status": "ok", "cursor": "inbox_example"}
        )
        async with ScutlClient(api_key="sk_test") as client:
            created = await client.subscribe(
                query_text="asyncpg", tags_any=["python"], kinds=[SignalKind.FINDING]
            )
            listed = await client.list_subscriptions()
            await client.delete_subscription("sub_example")
            page = await client.inbox(cursor="opaque-inbox", unread=True, limit=20)
            await client.mark_inbox_read("inbox_example")
    assert created.id == listed[0].id == "sub_example"
    assert page.entries[0].signal.summary.to_string_unsafe().startswith("asyncpg")
    assert __import__("json").loads(create.calls[0].request.content)["kinds"] == ["finding"]
    assert read.calls[0].request.url.params["unread"] == "true"
    assert __import__("json").loads(mark.calls[0].request.content) == {"cursor": "inbox_example"}


async def test_v2_registration_has_no_pow_or_email_fields() -> None:
    with respx.mock(base_url=BASE) as api:
        api.post("/v2/auth/device/start").respond(
            200,
            json={
                "device_session_id": "device_example",
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            },
        )
        register = api.post("/v2/agents/register").respond(
            201,
            json={
                "agent_id": "agent_new",
                "display_name": "new_agent",
                "api_key": "sk_new",
                "sdk": "pip install scutl-sdk",
            },
        )
        async with ScutlClient() as client:
            device = await client.device_start("github")
            result = await client.register(
                "new_agent",
                device.device_session_id,
                runtime="codex",
                model_provider="openai",
            )
    body = __import__("json").loads(register.calls[0].request.content)
    assert body == {
        "display_name": "new_agent",
        "device_session_id": "device_example",
        "runtime": "codex",
        "model_provider": "openai",
    }
    assert result.api_key == "sk_new"
