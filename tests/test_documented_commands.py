import ast
import html
import os
import re
import shlex
from pathlib import Path

import httpx

from scutl._cli import build_parser

_RETIRED = {
    "post",
    "repost",
    "delete-post",
    "get-post",
    "thread",
    "feed",
    "follow",
    "unfollow",
    "followers",
    "following",
    "create-filter",
    "list-filters",
    "delete-filter",
    "notifications",
    "notifications-read",
    "stats",
    "demo",
}


def _server_repo() -> Path:
    configured = os.environ.get("SCUTL_SERVER_REPO")
    if configured:
        return Path(configured).resolve()
    return (Path(__file__).resolve().parents[2] / "scutl").resolve()


def _json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _json_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _json_strings(child)]
    return []


def _document_sources() -> dict[str, str]:
    base_url = os.environ.get("SCUTL_SERVER_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, follow_redirects=True, timeout=10) as client:
            published = {}
            for name, path in {
                "/connect": "/connect",
                "/agent": "/agent",
                "/why": "/why",
            }.items():
                response = client.get(path, headers={"Accept": "application/json, text/html"})
                response.raise_for_status()
                published[name] = (
                    "\n".join(_json_strings(response.json()))
                    if name == "/agent"
                    else response.text
                )
        return {"README": Path("README.md").read_text(), **published}

    server = _server_repo()
    assert server.joinpath("src/scutl/main.py").exists(), (
        "Set SCUTL_SERVER_REPO to a checkout of scutl-sysop/scutl "
        "or SCUTL_SERVER_BASE_URL to a deployed server."
    )
    return {
        "README": Path("README.md").read_text(),
        "/connect": server.joinpath("src/scutl/templates/connect.html").read_text(),
        "/agent": server.joinpath("src/scutl/main.py").read_text(),
        "/why": server.joinpath("src/scutl/static/why.md").read_text(),
    }


def _commands(text: str, *, python_source: bool = False) -> list[str]:
    if python_source:
        tree = ast.parse(text)
        text = "\n".join(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "scutl-agent " in node.value
        )
    logical = re.sub(r"\\\s*\n\s*", " ", text)
    commands = []
    for line in logical.splitlines():
        clean = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        match = re.search(r"\bscutl-agent\s+(.+)", clean)
        if not match:
            continue
        command = ("scutl-agent " + match.group(1)).split("#", 1)[0].strip()
        if command:
            commands.append(command)
    return commands


def test_every_published_cli_example_parses_against_current_release():
    parser = build_parser()
    sources = _document_sources()
    parsed_by_source = {}
    for name, text in sources.items():
        examples = _commands(
            text,
            python_source=name == "/agent" and "SCUTL_SERVER_BASE_URL" not in os.environ,
        )
        parsed_by_source[name] = examples
        for example in examples:
            arguments = shlex.split(example)[1:]
            parsed = parser.parse_args(arguments)
            assert parsed.command not in _RETIRED, f"{name}: {example}"
    assert parsed_by_source["README"]
    assert parsed_by_source["/connect"]
    assert parsed_by_source["/agent"]
    assert parsed_by_source["/why"]
