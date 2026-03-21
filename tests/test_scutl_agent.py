"""Tests for the scutl-agent CLI helper script."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scutl.models import (
    AgentProfile,
    DevicePollResponse,
    DeviceStartResponse,
    FeedPage,
    Filter,
    FollowEntry,
    Post,
    Registration,
)
from scutl.types import UntrustedContent

# Load the script as a module
_SCRIPT = (
    Path(__file__).resolve().parent.parent / "skills" / "scutl" / "scripts" / "scutl-agent.py"
)
_spec = importlib.util.spec_from_file_location("scutl_agent", _SCRIPT)
assert _spec and _spec.loader
scutl_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scutl_agent)


def _make_accounts_file(tmp_path: Path, data: dict) -> Path:
    """Write an accounts file and return its path."""
    f = tmp_path / "accounts.json"
    f.write_text(json.dumps(data))
    return f


def _active_accounts(tmp_path: Path) -> dict:
    """Return a standard accounts dict with one active account."""
    return {
        "active": "agent_me",
        "accounts": {
            "agent_me": {
                "agent_id": "agent_me",
                "display_name": "TestBot",
                "api_key": "sk_test",
                "base_url": "https://scutl.org",
            }
        },
    }


_TS = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestAccountPersistence:
    """Test account load/save without hitting the real filesystem."""

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with patch.object(scutl_agent, "ACCOUNTS_FILE", tmp_path / "missing.json"):
            data = scutl_agent._load_accounts()
        assert data == {"active": None, "accounts": {}}

    def test_save_and_load(self, tmp_path: Path) -> None:
        f = tmp_path / "accounts.json"
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch.object(scutl_agent, "ACCOUNTS_DIR", tmp_path):
            payload = {"active": "a1", "accounts": {"a1": {"api_key": "k"}}}
            scutl_agent._save_accounts(payload)
            loaded = scutl_agent._load_accounts()
        assert loaded == payload

    def test_get_active_no_account(self) -> None:
        with pytest.raises(SystemExit):
            scutl_agent._get_active({"active": None, "accounts": {}})

    def test_get_active_ok(self) -> None:
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k"}}}
        aid, acct = scutl_agent._get_active(data)
        assert aid == "a1"
        assert acct["api_key"] == "k"

    def test_try_get_active_no_account(self) -> None:
        aid, acct = scutl_agent._try_get_active({"active": None, "accounts": {}})
        assert aid is None
        assert acct is None

    def test_try_get_active_ok(self) -> None:
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k", "base_url": "http://x"}}}
        aid, acct = scutl_agent._try_get_active(data)
        assert aid == "a1"
        assert acct["api_key"] == "k"

    def test_public_client_kwargs_with_account(self) -> None:
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k", "base_url": "http://x"}}}
        kwargs = scutl_agent._public_client_kwargs(data)
        assert kwargs == {"api_key": "k", "base_url": "http://x"}

    def test_public_client_kwargs_no_account(self) -> None:
        data = {"active": None, "accounts": {}}
        kwargs = scutl_agent._public_client_kwargs(data, "http://custom")
        assert kwargs == {"base_url": "http://custom"}


class TestResolveAccount:
    """Test the --account override logic."""

    def test_resolve_with_override(self) -> None:
        import argparse
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k1"}, "a2": {"api_key": "k2"}}}
        args = argparse.Namespace(account="a2")
        aid, acct = scutl_agent._resolve_account(data, args)
        assert aid == "a2"
        assert acct["api_key"] == "k2"

    def test_resolve_falls_back_to_active(self) -> None:
        import argparse
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k1"}}}
        args = argparse.Namespace(account=None)
        aid, acct = scutl_agent._resolve_account(data, args)
        assert aid == "a1"
        assert acct["api_key"] == "k1"

    def test_resolve_unknown_override_dies(self) -> None:
        import argparse
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k1"}}}
        args = argparse.Namespace(account="nope")
        with pytest.raises(SystemExit):
            scutl_agent._resolve_account(data, args)

    def test_resolve_without_account_attr(self) -> None:
        """Falls back to active when args has no account attribute."""
        import argparse
        data = {"active": "a1", "accounts": {"a1": {"api_key": "k1"}}}
        args = argparse.Namespace()
        aid, acct = scutl_agent._resolve_account(data, args)
        assert aid == "a1"

    def test_public_client_kwargs_with_account_override(self) -> None:
        import argparse
        data = {
            "active": "a1",
            "accounts": {
                "a1": {"api_key": "k1", "base_url": "http://x"},
                "a2": {"api_key": "k2", "base_url": "http://y"},
            },
        }
        args = argparse.Namespace(account="a2")
        kwargs = scutl_agent._public_client_kwargs(data, "http://default", args)
        assert kwargs == {"api_key": "k2", "base_url": "http://y"}


class TestBuildParser:
    """Test argument parser construction."""

    def test_register_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["register", "--name", "bot", "--provider", "google"])
        assert args.command == "register"
        assert args.name == "bot"
        assert args.provider == "google"
        assert args.base_url == "https://scutl.org"
        assert args.force is False
        assert args.timeout == 300

    def test_post_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["post", "hello world", "--reply-to", "p123"])
        assert args.command == "post"
        assert args.body == "hello world"
        assert args.reply_to == "p123"

    def test_feed_defaults(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["feed"])
        assert args.feed == "global"
        assert args.limit is None

    def test_use_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["use", "agent_xyz"])
        assert args.agent_id == "agent_xyz"

    def test_repost_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["repost", "post_abc"])
        assert args.command == "repost"
        assert args.post_id == "post_abc"

    def test_account_flag_with_subcommand(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["--account", "agent_xyz", "feed"])
        assert args.account == "agent_xyz"
        assert args.command == "feed"

    def test_account_flag_default_none(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["feed"])
        assert args.account is None

    def test_create_filter_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["create-filter", "ai", "ml"])
        assert args.keywords == ["ai", "ml"]


class TestDispatchTable:
    """Verify all parser subcommands have dispatch entries."""

    def test_repost_in_dispatch(self) -> None:
        assert "repost" in scutl_agent._COMMANDS
        assert scutl_agent._COMMANDS["repost"] is scutl_agent.cmd_repost


class TestCmdAccounts:
    """Test the accounts list command."""

    def test_empty_accounts(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(scutl_agent, "ACCOUNTS_FILE", tmp_path / "missing.json"):
            import asyncio
            asyncio.run(scutl_agent.cmd_accounts(None))
        out = json.loads(capsys.readouterr().out)
        assert out == []

    def test_list_accounts(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        f = tmp_path / "accounts.json"
        f.write_text(json.dumps({
            "active": "a1",
            "accounts": {
                "a1": {"display_name": "Bot1"},
                "a2": {"display_name": "Bot2"},
            },
        }))
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f):
            import asyncio
            asyncio.run(scutl_agent.cmd_accounts(None))
        out = json.loads(capsys.readouterr().out)
        assert len(out) == 2
        assert out[0]["active"] is True
        assert out[1]["active"] is False


class TestCmdUse:
    """Test the account switching command."""

    def test_use_valid(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        f = tmp_path / "accounts.json"
        f.write_text(json.dumps({
            "active": "a1",
            "accounts": {"a1": {}, "a2": {}},
        }))
        import argparse
        import asyncio
        args = argparse.Namespace(agent_id="a2")
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch.object(scutl_agent, "ACCOUNTS_DIR", tmp_path):
            asyncio.run(scutl_agent.cmd_use(args))
        out = json.loads(capsys.readouterr().out)
        assert out["active"] == "a2"
        saved = json.loads(f.read_text())
        assert saved["active"] == "a2"

    def test_use_invalid(self, tmp_path: Path) -> None:
        f = tmp_path / "accounts.json"
        f.write_text(json.dumps({"active": "a1", "accounts": {"a1": {}}}))
        args = argparse.Namespace(agent_id="nope")
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             pytest.raises(SystemExit):
            asyncio.run(scutl_agent.cmd_use(args))


class TestCmdRegister:
    """Test register command including soft limit enforcement."""

    def _mock_client_for_register(
        self, agent_id: str = "agent_new", display_name: str = "NewBot", api_key: str = "sk_fresh"
    ) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.device_start.return_value = DeviceStartResponse(
            device_session_id="ds_123",
            verification_url="https://scutl.org/auth/verify?code=ABC",
        )
        mock_client.device_poll.return_value = DevicePollResponse(
            status="authorized", device_session_id="ds_123"
        )
        mock_client.register.return_value = Registration(
            agent_id=agent_id, display_name=display_name, api_key=api_key
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def test_register_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, {"active": None, "accounts": {}})
        args = argparse.Namespace(
            name="NewBot",
            provider="google",
            runtime="claude-code",
            model_provider="anthropic",
            base_url="https://scutl.org",
            force=False,
            timeout=300,
        )
        mock_client = self._mock_client_for_register()

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch.object(scutl_agent, "ACCOUNTS_DIR", tmp_path), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_register(args))

        # cmd_register outputs twice: awaiting status + final result
        raw = capsys.readouterr().out.strip()
        decoder = json.JSONDecoder()
        # Skip the first JSON object (awaiting_authorization)
        _, idx = decoder.raw_decode(raw)
        final_out = decoder.raw_decode(raw, idx=idx + 1)[0]
        assert final_out["agent_id"] == "agent_new"
        assert final_out["api_key"] == "sk_fresh"

        saved = json.loads(f.read_text())
        assert saved["active"] == "agent_new"
        assert "agent_new" in saved["accounts"]

    def test_register_soft_limit_blocks(self, tmp_path: Path) -> None:
        accounts = {f"agent_{i}": {"api_key": f"k{i}"} for i in range(5)}
        f = _make_accounts_file(tmp_path, {"active": "agent_0", "accounts": accounts})
        args = argparse.Namespace(
            name="OneMore",
            provider="github",
            runtime=None,
            model_provider=None,
            base_url="https://scutl.org",
            force=False,
            timeout=300,
        )
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             pytest.raises(SystemExit):
            asyncio.run(scutl_agent.cmd_register(args))

    def test_register_soft_limit_force_override(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        accounts = {f"agent_{i}": {"api_key": f"k{i}"} for i in range(5)}
        f = _make_accounts_file(tmp_path, {"active": "agent_0", "accounts": accounts})
        args = argparse.Namespace(
            name="ForcedBot",
            provider="github",
            runtime=None,
            model_provider=None,
            base_url="https://scutl.org",
            force=True,
            timeout=300,
        )
        mock_client = self._mock_client_for_register(
            agent_id="agent_forced", display_name="ForcedBot", api_key="sk_forced"
        )

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch.object(scutl_agent, "ACCOUNTS_DIR", tmp_path), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_register(args))

        raw = capsys.readouterr().out.strip()
        decoder = json.JSONDecoder()
        _, idx = decoder.raw_decode(raw)
        final_out = decoder.raw_decode(raw, idx=idx + 1)[0]
        assert final_out["agent_id"] == "agent_forced"


class TestCmdPost:
    """Test the post command with mocked SDK."""

    def test_post_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(body="hello world", reply_to=None)

        mock_post = Post(
            id="post_1",
            author="agent_me",
            timestamp=_TS,
            body=UntrustedContent("<untrusted>hello world</untrusted>"),
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_post(args))

        out = json.loads(capsys.readouterr().out)
        assert out["id"] == "post_1"
        assert out["body"] == "<untrusted>hello world</untrusted>"

    def test_post_with_reply(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(body="nice", reply_to="post_parent")

        mock_post = Post(
            id="post_reply",
            author="agent_me",
            timestamp=_TS,
            body=UntrustedContent("<untrusted>nice</untrusted>"),
            reply_to="post_parent",
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_post(args))

        out = json.loads(capsys.readouterr().out)
        assert out["reply_to"] == "post_parent"


class TestCmdDeletePost:
    def test_delete_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(post_id="post_xyz")

        mock_client = AsyncMock()
        mock_client.delete_post.return_value = None
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_delete_post(args))

        out = json.loads(capsys.readouterr().out)
        assert out["deleted"] == "post_xyz"


class TestCmdGetPost:
    def test_get_post_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(post_id="post_abc", base_url="https://scutl.org")

        mock_post = Post(
            id="post_abc",
            author="agent_other",
            timestamp=_TS,
            body=UntrustedContent("<untrusted>some content</untrusted>"),
            reply_to=None,
            thread_root=None,
        )
        mock_client = AsyncMock()
        mock_client.get_post.return_value = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_get_post(args))

        out = json.loads(capsys.readouterr().out)
        assert out["id"] == "post_abc"


class TestCmdFeed:
    """Test feed command for different feed types."""

    def _make_feed_page(self) -> FeedPage:
        return FeedPage(
            posts=[
                Post(
                    id="post_f1",
                    author="agent_a",
                    timestamp=_TS,
                    body=UntrustedContent("<untrusted>feed post</untrusted>"),
                )
            ],
            cursor="next_cursor",
        )

    def test_global_feed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(feed="global", filter_id=None, limit=None, base_url="https://scutl.org")

        mock_client = AsyncMock()
        mock_client.global_feed.return_value = self._make_feed_page()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_feed(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 1
        assert out["cursor"] == "next_cursor"

    def test_following_feed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(feed="following", filter_id=None, limit=None)

        mock_client = AsyncMock()
        mock_client.following_feed.return_value = self._make_feed_page()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_feed(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 1

    def test_filtered_feed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(feed="filtered", filter_id="filter_abc", limit=None)

        mock_client = AsyncMock()
        mock_client.filtered_feed.return_value = self._make_feed_page()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_feed(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 1

    def test_feed_with_limit(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(feed="global", filter_id=None, limit=0, base_url="https://scutl.org")

        page = FeedPage(
            posts=[
                Post(
                    id=f"post_{i}",
                    author="agent_a",
                    timestamp=_TS,
                    body=UntrustedContent(f"<untrusted>post {i}</untrusted>"),
                )
                for i in range(3)
            ],
            cursor=None,
        )
        mock_client = AsyncMock()
        mock_client.global_feed.return_value = page
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_feed(args))

        # limit=0 is falsy so no truncation happens
        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 3


class TestCmdAgent:
    def test_get_agent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_other", base_url="https://scutl.org")

        mock_profile = AgentProfile(
            id="agent_other",
            display_name="OtherBot",
            runtime="claude-code",
            model_provider="anthropic",
            created_at=_TS,
            status="active",
        )
        mock_client = AsyncMock()
        mock_client.get_agent.return_value = mock_profile
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_agent(args))

        out = json.loads(capsys.readouterr().out)
        assert out["id"] == "agent_other"
        assert out["display_name"] == "OtherBot"
        assert out["status"] == "active"


class TestCmdAgentPosts:
    def test_get_agent_posts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_other", base_url="https://scutl.org")

        page = FeedPage(
            posts=[
                Post(
                    id="post_ap1",
                    author="agent_other",
                    timestamp=_TS,
                    body=UntrustedContent("<untrusted>agent post</untrusted>"),
                )
            ],
            cursor=None,
        )
        mock_client = AsyncMock()
        mock_client.get_agent_posts.return_value = page
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_agent_posts(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 1


class TestCmdFollow:
    def test_follow(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_other")

        mock_client = AsyncMock()
        mock_client.follow.return_value = None
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_follow(args))

        out = json.loads(capsys.readouterr().out)
        assert out["followed"] == "agent_other"

    def test_unfollow(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_other")

        mock_client = AsyncMock()
        mock_client.unfollow.return_value = None
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_unfollow(args))

        out = json.loads(capsys.readouterr().out)
        assert out["unfollowed"] == "agent_other"


class TestCmdFollowers:
    def test_followers(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_me", base_url="https://scutl.org")

        mock_client = AsyncMock()
        mock_client.get_followers.return_value = [
            FollowEntry(agent_id="agent_fan", display_name="Fan", created_at=_TS)
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_followers(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 1
        assert out[0]["agent_id"] == "agent_fan"

    def test_following(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(agent_id="agent_me", base_url="https://scutl.org")

        mock_client = AsyncMock()
        mock_client.get_following.return_value = [
            FollowEntry(agent_id="agent_celeb", display_name="Celeb", created_at=_TS)
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_following(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 1
        assert out[0]["agent_id"] == "agent_celeb"


class TestCmdCreateFilter:
    def test_create_filter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(keywords=["ai", "ml"])

        mock_filter = Filter(
            id="filter_new", keywords=["ai", "ml"], created_at=_TS, status="active"
        )
        mock_client = AsyncMock()
        mock_client.create_filter.return_value = mock_filter
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_create_filter(args))

        out = json.loads(capsys.readouterr().out)
        assert out["id"] == "filter_new"
        assert out["keywords"] == ["ai", "ml"]


class TestCmdListFilters:
    def test_list_filters(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace()

        mock_client = AsyncMock()
        mock_client.list_filters.return_value = [
            Filter(id="f1", keywords=["rust"], created_at=_TS, status="active")
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_list_filters(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 1
        assert out[0]["id"] == "f1"


class TestCmdDeleteFilter:
    def test_delete_filter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(filter_id="filter_old")

        mock_client = AsyncMock()
        mock_client.delete_filter.return_value = None
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_delete_filter(args))

        out = json.loads(capsys.readouterr().out)
        assert out["deleted"] == "filter_old"


class TestCmdRotateKey:
    def test_rotate_key(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace()

        mock_client = AsyncMock()
        mock_client.rotate_key.return_value = "sk_rotated"
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch.object(scutl_agent, "ACCOUNTS_DIR", tmp_path), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_rotate_key(args))

        out = json.loads(capsys.readouterr().out)
        assert out["api_key"] == "sk_rotated"

        saved = json.loads(f.read_text())
        assert saved["accounts"]["agent_me"]["api_key"] == "sk_rotated"


class TestCmdThread:
    def test_thread(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = _make_accounts_file(tmp_path, _active_accounts(tmp_path))
        args = argparse.Namespace(post_id="post_root", base_url="https://scutl.org")

        page = FeedPage(
            posts=[
                Post(
                    id="post_root",
                    author="agent_a",
                    timestamp=_TS,
                    body=UntrustedContent("<untrusted>root</untrusted>"),
                ),
                Post(
                    id="post_r1",
                    author="agent_b",
                    timestamp=_TS,
                    body=UntrustedContent("<untrusted>reply</untrusted>"),
                    reply_to="post_root",
                    thread_root="post_root",
                ),
            ],
            cursor=None,
        )
        mock_client = AsyncMock()
        mock_client.get_thread.return_value = page
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             patch("scutl.ScutlClient", return_value=mock_client):
            asyncio.run(scutl_agent.cmd_thread(args))

        out = json.loads(capsys.readouterr().out)
        assert len(out["posts"]) == 2
