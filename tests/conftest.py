"""Shared pytest configuration and fixtures."""

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests against live scutl.org API",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    run_integration = config.getoption("--run-integration") or os.environ.get(
        "SCUTL_INTEGRATION", ""
    ) == "1"
    if run_integration:
        return
    skip_integration = pytest.mark.skip(
        reason="Need --run-integration or SCUTL_INTEGRATION=1 to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
