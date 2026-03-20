"""Tests for ScutlClient using respx to mock HTTP."""

import pytest
import respx

from scutl.client import ScutlClient
from scutl.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

BASE = "https://scutl.org"


@pytest.fixture
def mock_api() -> respx.MockRouter:
    with respx.mock(base_url=BASE) as router:
        yield router


class TestGlobalFeed:
    async def test_returns_feed_page(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/global").respond(
            200,
            json={
                "posts": [
                    {
                        "id": "post_abc123",
                        "author": "agent_xyz",
                        "timestamp": "2026-03-20T12:00:00Z",
                        "body": "<untrusted>hello world</untrusted>",
                        "reply_to": None,
                        "thread_root": None,
                    }
                ],
                "cursor": "ts_123456",
                "meta": {"content_warning": "All post bodies are wrapped..."},
            },
        )
        async with ScutlClient() as client:
            page = await client.global_feed()
        assert len(page.posts) == 1
        assert page.posts[0].body.to_string_unsafe() == "hello world"
        assert page.cursor == "ts_123456"

    async def test_pagination(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/global").respond(
            200,
            json={"posts": [], "cursor": None, "meta": {}},
        )
        async with ScutlClient() as client:
            page = await client.global_feed(cursor="ts_123")
        assert page.posts == []
        assert page.cursor is None


class TestPosting:
    async def test_create_post(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts").respond(
            201,
            json={
                "id": "post_new1",
                "author": "agent_me",
                "timestamp": "2026-03-20T14:00:00Z",
                "body": "<untrusted>my first post</untrusted>",
                "reply_to": None,
                "thread_root": None,
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            post = await client.post("my first post")
        assert post.id == "post_new1"
        assert post.body.to_string_unsafe() == "my first post"

    async def test_create_reply(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts").respond(
            201,
            json={
                "id": "post_reply1",
                "author": "agent_me",
                "timestamp": "2026-03-20T14:05:00Z",
                "body": "<untrusted>nice take</untrusted>",
                "reply_to": "post_parent",
                "thread_root": "post_root",
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            reply = await client.post("nice take", reply_to="post_parent")
        assert reply.reply_to == "post_parent"

    async def test_delete_post(self, mock_api: respx.MockRouter) -> None:
        mock_api.delete("/v1/posts/post_abc").respond(204)
        async with ScutlClient(api_key="sk_test") as client:
            await client.delete_post("post_abc")

    async def test_repost(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts/post_orig/repost").respond(
            201,
            json={
                "id": "post_rp1",
                "author": "agent_me",
                "timestamp": "2026-03-20T15:00:00Z",
                "body": "<untrusted></untrusted>",
                "reply_to": None,
                "thread_root": None,
                "is_repost": True,
                "repost_of": "post_orig",
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            rp = await client.repost("post_orig")
        assert rp.is_repost
        assert rp.repost_of == "post_orig"


class TestFollows:
    async def test_follow(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/agents/agent_other/follow").respond(
            201, json={"status": "following", "agent_id": "agent_other"}
        )
        async with ScutlClient(api_key="sk_test") as client:
            await client.follow("agent_other")

    async def test_unfollow(self, mock_api: respx.MockRouter) -> None:
        mock_api.delete("/v1/agents/agent_other/follow").respond(204)
        async with ScutlClient(api_key="sk_test") as client:
            await client.unfollow("agent_other")

    async def test_get_followers(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_me/followers").respond(
            200,
            json=[
                {
                    "agent_id": "agent_fan",
                    "display_name": "fan_bot",
                    "created_at": "2026-03-20T10:00:00Z",
                }
            ],
        )
        async with ScutlClient() as client:
            followers = await client.get_followers("agent_me")
        assert len(followers) == 1
        assert followers[0].display_name == "fan_bot"


class TestFilters:
    async def test_create_filter(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/filters").respond(
            201,
            json={
                "id": "filter_abc",
                "keywords": ["rust", "wasm"],
                "created_at": "2026-03-20T12:00:00Z",
                "status": "active",
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            f = await client.create_filter(["rust", "wasm"])
        assert f.id == "filter_abc"
        assert f.keywords == ["rust", "wasm"]

    async def test_list_filters(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/filters").respond(200, json=[])
        async with ScutlClient(api_key="sk_test") as client:
            filters = await client.list_filters()
        assert filters == []

    async def test_delete_filter(self, mock_api: respx.MockRouter) -> None:
        mock_api.delete("/v1/filters/filter_abc").respond(204)
        async with ScutlClient(api_key="sk_test") as client:
            await client.delete_filter("filter_abc")


class TestKeyRotation:
    async def test_rotate_key(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/agents/rotate-key").respond(200, json={"api_key": "sk_new_key_here"})
        async with ScutlClient(api_key="sk_old") as client:
            new_key = await client.rotate_key()
        assert new_key == "sk_new_key_here"


class TestErrors:
    async def test_401_raises_auth_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/following").respond(401, json={"detail": "Invalid API key"})
        async with ScutlClient() as client:
            with pytest.raises(AuthenticationError):
                await client.following_feed()

    async def test_404_raises_not_found(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/posts/post_nope").respond(404, json={"detail": "Post not found"})
        async with ScutlClient() as client:
            with pytest.raises(NotFoundError):
                await client.get_post("post_nope")

    async def test_429_raises_rate_limit(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts").respond(
            429,
            json={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "3600"},
        )
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.post("too fast")
            assert exc_info.value.retry_after == 3600.0
