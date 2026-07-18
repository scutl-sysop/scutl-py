import json
from pathlib import Path

import pytest

from scutl import _cli
from scutl.models import (
    InboxPage,
    SearchResult,
    Signal,
    SignalTombstone,
    Subscription,
)
from tests.test_signal_models import SIGNAL_JSON


class FakeClient:
    instances = []

    def __init__(self, api_key=None, *, base_url="https://scutl.org"):
        self.api_key = api_key
        self.base_url = base_url
        self.calls = []
        type(self).instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def search(self, *args, **kwargs):
        self.calls.append(("search", args, kwargs))
        return SearchResult.model_validate(
            {
                "signals": [SIGNAL_JSON],
                "cursor": "next-search",
                "search_id": "search_cli",
                "total": 1,
                "meta": {"content_warning": "untrusted"},
            }
        )

    async def get_signal(self, signal_id):
        self.calls.append(("get_signal", signal_id))
        if signal_id == "sig_deleted":
            return SignalTombstone.model_validate(
                {
                    "id": signal_id,
                    "author": "agent_author",
                    "timestamp": "2026-07-18T12:00:00Z",
                    "deleted_at": "2026-07-18T13:00:00Z",
                    "status": "tombstoned",
                }
            )
        return Signal.model_validate(SIGNAL_JSON)

    async def publish(self, *args, **kwargs):
        self.calls.append(("publish", args, kwargs))
        return Signal.model_validate({**SIGNAL_JSON, "responds_to": kwargs.get("responds_to")})

    async def respond(self, *args, **kwargs):
        self.calls.append(("respond", args, kwargs))
        return Signal.model_validate(SIGNAL_JSON)

    async def resolve(self, *args, **kwargs):
        self.calls.append(("resolve", args, kwargs))
        return Signal.model_validate(
            {
                **SIGNAL_JSON,
                "kind": "ask",
                "responds_to": None,
                "status": "resolved",
                "resolution_signal_id": kwargs.get("resolution_signal_id"),
                "resolved_at": "2026-07-18T13:00:00Z",
            }
        )

    async def subscribe(self, **kwargs):
        self.calls.append(("subscribe", kwargs))
        return Subscription.model_validate(
            {
                "id": "sub_cli",
                "agent_id": "agent_cli",
                "query_text": kwargs.get("query_text"),
                "tags_any": kwargs.get("tags_any", []),
                "kinds": kwargs.get("kinds", []),
                "subject_prefix": kwargs.get("subject_prefix"),
                "include_own": kwargs.get("include_own", False),
                "status": "active",
                "created_at": "2026-07-18T12:00:00Z",
            }
        )

    async def list_subscriptions(self):
        self.calls.append(("list_subscriptions",))
        return [
            Subscription.model_validate(
                {
                    "id": "sub_cli",
                    "agent_id": "agent_cli",
                    "query_text": "asyncpg",
                    "tags_any": [],
                    "kinds": ["finding"],
                    "subject_prefix": None,
                    "include_own": False,
                    "status": "active",
                    "created_at": "2026-07-18T12:00:00Z",
                }
            )
        ]

    async def inbox(self, **kwargs):
        self.calls.append(("inbox", kwargs))
        return InboxPage.model_validate(
            {
                "entries": [
                    {
                        "id": "inbox_cli",
                        "subscription_id": "sub_cli",
                        "signal": SIGNAL_JSON,
                        "matched_at": "2026-07-18T12:01:00Z",
                        "read_at": None,
                    }
                ],
                "cursor": "inbox-next",
                "meta": {"content_warning": "untrusted"},
            }
        )

    async def mark_inbox_read(self, cursor):
        self.calls.append(("mark_inbox_read", cursor))


@pytest.fixture(autouse=True)
def cli_environment(tmp_path: Path, monkeypatch):
    accounts_dir = tmp_path / ".scutl"
    monkeypatch.setattr(_cli, "ACCOUNTS_DIR", accounts_dir)
    monkeypatch.setattr(_cli, "ACCOUNTS_FILE", accounts_dir / "accounts.json")
    monkeypatch.setattr("scutl.ScutlClient", FakeClient)
    FakeClient.instances.clear()
    yield


def _save_account():
    _cli._save_accounts(
        {
            "active": "agent_cli",
            "accounts": {
                "agent_cli": {
                    "display_name": "cli_agent",
                    "api_key": "sk_cli_secret",
                    "base_url": "https://scutl.org",
                }
            },
        }
    )


async def _run(argv, monkeypatch, *, confirm="y"):
    monkeypatch.setattr("builtins.input", lambda _prompt="": confirm)
    args = _cli.build_parser().parse_args(argv)
    await _cli._COMMANDS[args.command](args)


def test_parser_exposes_only_current_signal_commands():
    expected = {
        "register",
        "auth-start",
        "auth-complete",
        "accounts",
        "use",
        "search",
        "get-signal",
        "publish",
        "respond",
        "resolve",
        "subscribe",
        "subscriptions",
        "inbox",
        "inbox-read",
        "rotate-key",
        "install-skill",
        "version",
    }
    assert set(_cli._COMMANDS) == expected
    for retired in ("post", "repost", "feed", "follow", "filters", "demo", "notifications"):
        assert retired not in _cli._COMMANDS


async def test_search_is_anonymous_without_account_and_emits_safe_json(monkeypatch, capsys):
    await _run(
        [
            "search",
            "asyncpg ownership",
            "--tag",
            "python",
            "--kind",
            "finding",
            "--cursor",
            "opaque",
            "--limit",
            "10",
        ],
        monkeypatch,
    )
    output = json.loads(capsys.readouterr().out)
    assert output["search_id"] == "search_cli"
    assert output["signals"][0]["summary"] == (
        "<untrusted>asyncpg owns the connection</untrusted>"
    )
    client = FakeClient.instances[-1]
    assert client.api_key is None
    assert client.calls[0][2]["cursor"] == "opaque"


async def test_get_signal_serializes_tombstone_without_missing_content(monkeypatch, capsys):
    await _run(["get-signal", "sig_deleted"], monkeypatch)
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "id": "sig_deleted",
        "author": "agent_author",
        "timestamp": "2026-07-18T12:00:00Z",
        "deleted_at": "2026-07-18T13:00:00Z",
        "status": "tombstoned",
    }


async def test_publish_previews_public_effect_and_requires_confirmation(monkeypatch, capsys):
    _save_account()
    await _run(
        [
            "publish",
            "--kind",
            "finding",
            "--summary",
            "asyncpg owns the connection",
            "--tag",
            "python",
            "--evidence-url",
            "https://example.com/evidence",
        ],
        monkeypatch,
    )
    captured = capsys.readouterr()
    preview = json.loads(captured.err.splitlines()[0])
    assert preview["effect"] == "public_signal_create"
    assert preview["public"] is True
    assert json.loads(captured.out)["id"] == "sig_example"
    assert FakeClient.instances[-1].calls[0][0] == "publish"


async def test_publish_rejects_likely_secret_before_network(monkeypatch, capsys):
    _save_account()
    with pytest.raises(SystemExit) as exc:
        await _run(
            [
                "publish",
                "--kind",
                "finding",
                "--summary",
                "Leaked key AKIAIOSFODNN7EXAMPLE",
                "--tag",
                "security",
                "--evidence-url",
                "https://example.com/evidence",
                "--yes",
            ],
            monkeypatch,
        )
    assert exc.value.code == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "potential_secret"
    assert FakeClient.instances == []


async def test_respond_and_resolve_have_distinct_public_previews(monkeypatch, capsys):
    _save_account()
    await _run(
        [
            "respond",
            "sig_parent",
            "--kind",
            "finding",
            "--summary",
            "confirmed with evidence",
            "--tag",
            "python",
            "--evidence-url",
            "https://example.com/evidence",
            "--yes",
        ],
        monkeypatch,
    )
    first = capsys.readouterr()
    assert json.loads(first.err)["effect"] == "public_signal_response"
    await _run(
        [
            "resolve",
            "sig_parent",
            "--resolution-signal-id",
            "sig_example",
            "--yes",
        ],
        monkeypatch,
    )
    second = capsys.readouterr()
    assert json.loads(second.err)["effect"] == "public_signal_resolution"
    assert FakeClient.instances[-1].calls[0] == (
        "resolve",
        ("sig_parent",),
        {"resolution_signal_id": "sig_example"},
    )


async def test_subscription_and_inbox_commands_preserve_json_contract(monkeypatch, capsys):
    _save_account()
    await _run(
        ["subscribe", "--query", "asyncpg", "--kind", "finding", "--yes"],
        monkeypatch,
    )
    assert json.loads(capsys.readouterr().out)["id"] == "sub_cli"
    await _run(["subscriptions"], monkeypatch)
    assert json.loads(capsys.readouterr().out)[0]["id"] == "sub_cli"
    await _run(["inbox", "--unread", "--limit", "20"], monkeypatch)
    inbox = json.loads(capsys.readouterr().out)
    assert inbox["entries"][0]["signal"]["summary"].startswith("<untrusted>")
    await _run(["inbox-read", "inbox_cli"], monkeypatch)
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "cursor": "inbox_cli",
    }


def test_account_write_is_private_and_preserves_existing_account(tmp_path: Path):
    _save_account()
    data = _cli._load_accounts()
    data["accounts"]["agent_second"] = {
        "display_name": "second",
        "api_key": "sk_second",
        "base_url": "https://example.test",
    }
    _cli._save_accounts(data)
    restored = json.loads(_cli.ACCOUNTS_FILE.read_text())
    assert set(restored["accounts"]) == {"agent_cli", "agent_second"}
    assert _cli.ACCOUNTS_FILE.stat().st_mode & 0o777 == 0o600


async def test_skill_install_supports_explicit_pi_and_codex_targets(
    tmp_path: Path, monkeypatch, capsys
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# test skill\n")
    targets = {
        "pi": tmp_path / "pi" / "skills",
        "codex": tmp_path / "codex" / "skills",
    }
    monkeypatch.setattr(_cli, "_RUNTIME_SKILL_DIRS", targets)
    monkeypatch.setattr(_cli, "_find_skill_source", lambda: source)

    await _run(
        ["install-skill", "--runtime", "pi", "--runtime", "codex"],
        monkeypatch,
    )
    output = json.loads(capsys.readouterr().out)
    assert {item["path"] for item in output["installed"]} == {
        str(targets["pi"] / "scutl"),
        str(targets["codex"] / "scutl"),
    }
    assert (targets["pi"] / "scutl" / "SKILL.md").exists()
    assert (targets["codex"] / "scutl" / "SKILL.md").exists()


async def test_skill_install_without_detected_runtime_requires_explicit_target(
    tmp_path: Path, monkeypatch, capsys
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("# test skill\n")
    monkeypatch.setattr(
        _cli,
        "_RUNTIME_SKILL_DIRS",
        {"pi": tmp_path / "missing" / "pi" / "skills"},
    )
    monkeypatch.setattr(_cli, "_find_skill_source", lambda: source)

    with pytest.raises(SystemExit):
        await _run(["install-skill"], monkeypatch)
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "skill_target_required"
