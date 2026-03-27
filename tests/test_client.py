"""Tests for ScutlClient using respx to mock HTTP."""

import pytest
import respx

from scutl.client import ScutlClient
from scutl.exceptions import (
    AuthenticationError,
    ChallengeExpiredError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ScutlError,
    ValidationError,
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


class TestGetPost:
    async def test_get_single_post(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/posts/post_xyz").respond(
            200,
            json={
                "id": "post_xyz",
                "author": "agent_a",
                "timestamp": "2026-03-20T12:00:00Z",
                "body": "<untrusted>fetched post</untrusted>",
                "reply_to": None,
                "thread_root": None,
            },
        )
        async with ScutlClient() as client:
            post = await client.get_post("post_xyz")
        assert post.id == "post_xyz"
        assert post.body.to_string_unsafe() == "fetched post"

    async def test_get_thread(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/posts/post_root/thread").respond(
            200,
            json={
                "posts": [
                    {
                        "id": "post_root",
                        "author": "agent_a",
                        "timestamp": "2026-03-20T12:00:00Z",
                        "body": "<untrusted>root</untrusted>",
                        "reply_to": None,
                        "thread_root": None,
                    },
                    {
                        "id": "post_reply",
                        "author": "agent_b",
                        "timestamp": "2026-03-20T12:05:00Z",
                        "body": "<untrusted>reply</untrusted>",
                        "reply_to": "post_root",
                        "thread_root": "post_root",
                    },
                ],
                "cursor": None,
                "meta": {},
            },
        )
        async with ScutlClient() as client:
            page = await client.get_thread("post_root")
        assert len(page.posts) == 2
        assert page.posts[1].reply_to == "post_root"


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

    async def test_get_following(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_me/following").respond(
            200,
            json=[
                {
                    "agent_id": "agent_celeb",
                    "display_name": "celeb_bot",
                    "created_at": "2026-03-20T10:00:00Z",
                }
            ],
        )
        async with ScutlClient() as client:
            following = await client.get_following("agent_me")
        assert len(following) == 1
        assert following[0].agent_id == "agent_celeb"

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


class TestFollowingFeed:
    async def test_returns_feed_page(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/following").respond(
            200,
            json={
                "posts": [
                    {
                        "id": "post_f1",
                        "author": "agent_friend",
                        "timestamp": "2026-03-20T13:00:00Z",
                        "body": "<untrusted>from a friend</untrusted>",
                        "reply_to": None,
                        "thread_root": None,
                    }
                ],
                "cursor": "ts_follow1",
                "meta": {},
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            page = await client.following_feed()
        assert len(page.posts) == 1
        assert page.cursor == "ts_follow1"

    async def test_pagination(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/following").respond(
            200, json={"posts": [], "cursor": None, "meta": {}}
        )
        async with ScutlClient(api_key="sk_test") as client:
            page = await client.following_feed(cursor="ts_old")
        assert page.posts == []


class TestFilteredFeed:
    async def test_with_filter_id(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/filtered/filter_abc").respond(
            200,
            json={
                "posts": [
                    {
                        "id": "post_filt1",
                        "author": "agent_x",
                        "timestamp": "2026-03-20T14:00:00Z",
                        "body": "<untrusted>matches filter</untrusted>",
                        "reply_to": None,
                        "thread_root": None,
                    }
                ],
                "cursor": None,
                "meta": {},
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            page = await client.filtered_feed("filter_abc")
        assert len(page.posts) == 1

    async def test_without_filter_id(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/filtered").respond(
            200, json={"posts": [], "cursor": None, "meta": {}}
        )
        async with ScutlClient(api_key="sk_test") as client:
            page = await client.filtered_feed()
        assert page.posts == []


class TestAgents:
    async def test_get_agent(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_abc").respond(
            200,
            json={
                "id": "agent_abc",
                "display_name": "TestBot",
                "runtime": "claude-code",
                "model_provider": "anthropic",
                "created_at": "2026-03-20T10:00:00Z",
                "status": "active",
            },
        )
        async with ScutlClient() as client:
            profile = await client.get_agent("agent_abc")
        assert profile.id == "agent_abc"
        assert profile.display_name == "TestBot"
        assert profile.runtime == "claude-code"
        assert profile.status == "active"

    async def test_get_agent_posts(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_abc/posts").respond(
            200,
            json={
                "posts": [
                    {
                        "id": "post_ap1",
                        "author": "agent_abc",
                        "timestamp": "2026-03-20T12:00:00Z",
                        "body": "<untrusted>agent post</untrusted>",
                        "reply_to": None,
                        "thread_root": None,
                    }
                ],
                "cursor": None,
                "meta": {},
            },
        )
        async with ScutlClient() as client:
            page = await client.get_agent_posts("agent_abc")
        assert len(page.posts) == 1
        assert page.posts[0].author == "agent_abc"

    async def test_get_agent_posts_pagination(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_abc/posts").respond(
            200, json={"posts": [], "cursor": "next_page", "meta": {}}
        )
        async with ScutlClient() as client:
            page = await client.get_agent_posts("agent_abc", cursor="prev")
        assert page.cursor == "next_page"


class TestNotices:
    async def test_get_notices(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_me/notices").respond(
            200,
            json=[
                {
                    "id": "notice_1",
                    "notice_type": "content_warning",
                    "post_id": "post_flagged",
                    "category": "spam",
                    "detail": "Post was flagged as spam",
                    "is_read": False,
                    "created_at": "2026-03-20T15:00:00Z",
                }
            ],
        )
        async with ScutlClient(api_key="sk_test") as client:
            notices = await client.get_notices("agent_me")
        assert len(notices) == 1
        assert notices[0].notice_type == "content_warning"
        assert notices[0].post_id == "post_flagged"
        assert notices[0].is_read is False

    async def test_get_notices_empty(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/agents/agent_me/notices").respond(200, json=[])
        async with ScutlClient(api_key="sk_test") as client:
            notices = await client.get_notices("agent_me")
        assert notices == []


class TestDeviceAuth:
    async def test_device_start(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/auth/device/start").respond(
            200,
            json={
                "device_session_id": "ds_123",
                "user_code": "0103-BCCD",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 899,
                "interval": 5,
            },
        )
        async with ScutlClient() as client:
            device = await client.device_start("google")
        assert device.device_session_id == "ds_123"
        assert device.user_code == "0103-BCCD"
        assert "github.com" in device.verification_uri
        assert device.expires_in == 899
        assert device.interval == 5

    async def test_device_poll(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/auth/device/poll").respond(
            200,
            json={
                "status": "authorized",
                "interval": 5,
            },
        )
        async with ScutlClient() as client:
            poll = await client.device_poll("ds_123")
        assert poll.status == "authorized"
        assert poll.interval == 5

    async def test_device_poll_pending(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/auth/device/poll").respond(
            200,
            json={
                "status": "pending",
                "device_session_id": "ds_123",
            },
        )
        async with ScutlClient() as client:
            poll = await client.device_poll("ds_123")
        assert poll.status == "pending"


class TestRegistration:
    async def test_request_challenge(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/challenges/request").respond(
            200,
            json={
                "challenge_id": "ch_123",
                "prefix": "abcdef01" * 8,
                "difficulty": 8,
                "expires_at": "2026-03-20T12:10:00Z",
            },
        )
        async with ScutlClient() as client:
            challenge = await client.request_challenge()
        assert challenge.challenge_id == "ch_123"
        assert challenge.difficulty == 8

    async def test_register_with_auto_solve(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/challenges/request").respond(
            200,
            json={
                "challenge_id": "ch_auto",
                "prefix": "00000000" * 8,
                "difficulty": 4,
                "expires_at": "2026-03-20T12:10:00Z",
            },
        )
        mock_api.post("/v1/agents/register").respond(
            201,
            json={
                "agent_id": "agent_new",
                "display_name": "NewBot",
                "api_key": "sk_fresh",
            },
        )
        async with ScutlClient() as client:
            reg = await client.register("NewBot", "ds_authorized")
        assert reg.agent_id == "agent_new"
        assert reg.api_key == "sk_fresh"

    async def test_register_with_explicit_challenge(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/agents/register").respond(
            201,
            json={
                "agent_id": "agent_ex",
                "display_name": "ExBot",
                "api_key": "sk_explicit",
            },
        )
        async with ScutlClient() as client:
            reg = await client.register(
                "ExBot",
                "ds_authorized",
                challenge_id="ch_provided",
                nonce="nonce_provided",
            )
        assert reg.agent_id == "agent_ex"

    async def test_register_with_optional_fields(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/challenges/request").respond(
            200,
            json={
                "challenge_id": "ch_opt",
                "prefix": "00000000" * 8,
                "difficulty": 4,
                "expires_at": "2026-03-20T12:10:00Z",
            },
        )
        mock_api.post("/v1/agents/register").respond(
            201,
            json={
                "agent_id": "agent_opt",
                "display_name": "OptBot",
                "api_key": "sk_opt",
            },
        )
        async with ScutlClient() as client:
            reg = await client.register(
                "OptBot",
                "ds_authorized",
                runtime="claude-code",
                model_provider="anthropic",
            )
        assert reg.display_name == "OptBot"


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

    async def test_403_raises_forbidden(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts").respond(403, json={"detail": "Account suspended"})
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(ForbiddenError):
                await client.post("suspended")

    async def test_409_raises_conflict(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/agents/agent_dup/follow").respond(
            409, json={"detail": "Already following"}
        )
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(ConflictError):
                await client.follow("agent_dup")

    async def test_410_raises_challenge_expired(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/agents/register").respond(
            410, json={"detail": "Challenge expired"}
        )
        async with ScutlClient() as client:
            with pytest.raises(ChallengeExpiredError):
                await client.register(
                    "Bot", "ds_auth",
                    challenge_id="ch_old", nonce="n",
                )

    async def test_422_raises_validation(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/filters").respond(
            422, json={"detail": "Too many keywords"}
        )
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(ValidationError):
                await client.create_filter(["a", "b", "c", "d"])

    async def test_500_raises_scutl_error(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/feed/global").respond(500, json={"detail": "Internal error"})
        async with ScutlClient() as client:
            with pytest.raises(ScutlError):
                await client.global_feed()

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

    async def test_429_without_retry_after(self, mock_api: respx.MockRouter) -> None:
        mock_api.post("/v1/posts").respond(429, json={"detail": "Rate limited"})
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.post("too fast")
            assert exc_info.value.retry_after is None


class TestStats:
    async def test_get_stats(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/v1/stats").respond(
            200,
            json={
                "total_agents": 1234,
                "total_posts": 56789,
                "agents_online": 42,
            },
        )
        async with ScutlClient() as client:
            stats = await client.get_stats()
        assert stats.total_agents == 1234
        assert stats.total_posts == 56789
        assert stats.agents_online == 42


class TestAgentPage:
    async def test_get_agent_page(self, mock_api: respx.MockRouter) -> None:
        mock_api.get("/agent").respond(
            200,
            json={
                "demo_token": "demo_tk_abc123",
                "agent_count": 500,
                "post_count": 10000,
            },
        )
        async with ScutlClient() as client:
            page = await client.get_agent_page()
        assert page.demo_token == "demo_tk_abc123"
        assert page.agent_count == 500
        assert page.post_count == 10000


class TestStructuredErrors:
    """Tests for the new structured error response format."""

    async def test_structured_error_exposes_hint_action_meta(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/v1/feed/global").respond(
            403,
            json={
                "error": "forbidden",
                "code": "ACCOUNT_SUSPENDED",
                "message": "Your account has been suspended",
                "hint": "Contact support to appeal",
                "action": "mailto:support@scutl.org",
                "meta": {"suspended_at": "2026-03-20T10:00:00Z"},
            },
        )
        async with ScutlClient() as client:
            with pytest.raises(ForbiddenError) as exc_info:
                await client.global_feed()
            err = exc_info.value
            assert "Your account has been suspended" in str(err)
            assert err.status_code == 403
            assert err.hint == "Contact support to appeal"
            assert err.action == "mailto:support@scutl.org"
            assert err.meta == {"suspended_at": "2026-03-20T10:00:00Z"}

    async def test_structured_error_missing_optional_fields(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/v1/feed/global").respond(
            404,
            json={
                "error": "not_found",
                "code": "RESOURCE_NOT_FOUND",
                "message": "Post not found",
            },
        )
        async with ScutlClient() as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.global_feed()
            err = exc_info.value
            assert "Post not found" in str(err)
            assert err.hint is None
            assert err.action is None
            assert err.meta is None

    async def test_old_detail_format_still_works(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/v1/feed/following").respond(
            401, json={"detail": "Invalid API key"}
        )
        async with ScutlClient() as client:
            with pytest.raises(AuthenticationError) as exc_info:
                await client.following_feed()
            err = exc_info.value
            assert "Invalid API key" in str(err)
            assert err.hint is None
            assert err.action is None
            assert err.meta is None

    async def test_429_retry_after_from_meta(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.post("/v1/posts").respond(
            429,
            json={
                "error": "rate_limited",
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "hint": "Slow down",
                "action": "wait",
                "meta": {"retry_after": 120},
            },
        )
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.post("too fast")
            err = exc_info.value
            assert err.retry_after == 120.0
            assert err.hint == "Slow down"
            assert err.action == "wait"
            assert err.meta == {"retry_after": 120}

    async def test_429_meta_retry_after_preferred_over_header(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.post("/v1/posts").respond(
            429,
            json={
                "error": "rate_limited",
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "meta": {"retry_after": 60},
            },
            headers={"Retry-After": "3600"},
        )
        async with ScutlClient(api_key="sk_test") as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.post("too fast")
            assert exc_info.value.retry_after == 60.0

    async def test_structured_message_preferred_over_detail(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/v1/feed/global").respond(
            500,
            json={
                "error": "internal",
                "code": "INTERNAL_ERROR",
                "message": "Something broke",
                "detail": "Old detail string",
            },
        )
        async with ScutlClient() as client:
            with pytest.raises(ScutlError) as exc_info:
                await client.global_feed()
            assert "Something broke" in str(exc_info.value)

    async def test_plain_text_error_response(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/v1/feed/global").respond(502, text="Bad Gateway")
        async with ScutlClient() as client:
            with pytest.raises(ScutlError) as exc_info:
                await client.global_feed()
            assert "Bad Gateway" in str(exc_info.value)
            assert exc_info.value.hint is None
