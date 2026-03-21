"""Integration tests against the live scutl.org API.

Run with:
    pytest tests/test_integration.py --run-integration
or:
    SCUTL_INTEGRATION=1 pytest tests/test_integration.py
"""

import pytest

from scutl.client import ScutlClient
from scutl.models import Challenge, DevicePollResponse, DeviceStartResponse, FeedPage

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    async with ScutlClient() as c:
        yield c


class TestChallenge:
    async def test_request_challenge(self, client: ScutlClient) -> None:
        challenge = await client.request_challenge()
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_id
        assert challenge.prefix
        assert challenge.difficulty > 0
        assert challenge.expires_at is not None


class TestDeviceAuth:
    async def test_device_start_github(self, client: ScutlClient) -> None:
        resp = await client.device_start("github")
        assert isinstance(resp, DeviceStartResponse)
        assert resp.device_session_id
        assert resp.user_code
        assert resp.verification_uri.startswith("https")
        assert resp.expires_in > 0
        assert resp.interval > 0

    async def test_device_poll_pending(self, client: ScutlClient) -> None:
        start = await client.device_start("github")
        poll = await client.device_poll(start.device_session_id)
        assert isinstance(poll, DevicePollResponse)
        assert poll.status == "pending"
        assert poll.interval > 0


class TestGlobalFeed:
    async def test_global_feed_parses(self, client: ScutlClient) -> None:
        page = await client.global_feed()
        assert isinstance(page, FeedPage)
        assert isinstance(page.posts, list)
        # cursor may be None if there are no posts, but the field exists
        assert hasattr(page, "cursor")

    async def test_global_feed_posts_have_expected_fields(
        self, client: ScutlClient
    ) -> None:
        page = await client.global_feed()
        if not page.posts:
            pytest.skip("Global feed is empty, cannot validate post fields")
        post = page.posts[0]
        assert post.id
        assert post.author
        assert post.timestamp is not None
        assert post.body is not None
        assert len(post.body) >= 0
