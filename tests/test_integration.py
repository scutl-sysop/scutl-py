"""Opt-in integration tests against the deployed public v2 API."""

import pytest

from scutl.client import ScutlClient
from scutl.models import SearchResult

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    async with ScutlClient() as instance:
        yield instance


async def test_anonymous_search_parses_current_contract(client: ScutlClient) -> None:
    result = await client.search("asyncpg connection ownership", limit=5)
    assert isinstance(result, SearchResult)
    assert result.total >= 0
    assert result.search_id.startswith("search_")
    assert len(result.signals) <= 5


async def test_empty_query_returns_bounded_recent_signals(client: ScutlClient) -> None:
    result = await client.search(limit=3)
    assert len(result.signals) <= 3
    assert hasattr(result, "cursor")
