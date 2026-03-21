"""Tests for the scutl-agent CLI helper script."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Load the script as a module
_SCRIPT = (
    Path(__file__).resolve().parent.parent / "skills" / "scutl" / "scripts" / "scutl-agent.py"
)
_spec = importlib.util.spec_from_file_location("scutl_agent", _SCRIPT)
assert _spec and _spec.loader
scutl_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scutl_agent)


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


class TestBuildParser:
    """Test argument parser construction."""

    def test_register_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["register", "--name", "bot", "--email", "a@b.com"])
        assert args.command == "register"
        assert args.name == "bot"
        assert args.email == "a@b.com"
        assert args.base_url == "https://scutl.org"
        assert args.force is False

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

    def test_create_filter_args(self) -> None:
        parser = scutl_agent.build_parser()
        args = parser.parse_args(["create-filter", "ai", "ml"])
        assert args.keywords == ["ai", "ml"]


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
        import argparse
        import asyncio
        args = argparse.Namespace(agent_id="nope")
        with patch.object(scutl_agent, "ACCOUNTS_FILE", f), \
             pytest.raises(SystemExit):
            asyncio.run(scutl_agent.cmd_use(args))
