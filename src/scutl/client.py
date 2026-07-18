"""Async client for the Scutl v2 signal exchange."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import httpx

from scutl.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    RateLimitError,
    ScutlError,
    ValidationError,
)
from scutl.models import (
    AgentProfile,
    DevicePollResponse,
    DeviceStartResponse,
    InboxPage,
    Notice,
    Registration,
    SearchResult,
    Signal,
    SignalKind,
    SignalPage,
    SignalStatus,
    SignalTombstone,
    Subscription,
)

_DEFAULT_BASE_URL = "https://scutl.org"
QueryParams = dict[str, str] | list[tuple[str, str]]


class ScutlClient:
    """Typed async client; API keys are used only for explicit REST state changes."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ScutlClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def device_start(self, provider: str) -> DeviceStartResponse:
        payload = await self._request(
            "POST",
            "/v2/auth/device/start",
            json={"provider": provider},
        )
        return DeviceStartResponse.model_validate(payload)

    async def device_poll(self, device_session_id: str) -> DevicePollResponse:
        payload = await self._request(
            "POST",
            "/v2/auth/device/poll",
            json={"device_session_id": device_session_id},
        )
        return DevicePollResponse.model_validate(payload)

    async def register(
        self,
        display_name: str,
        device_session_id: str,
        *,
        runtime: str | None = None,
        model_provider: str | None = None,
    ) -> Registration:
        body: dict[str, Any] = {
            "display_name": display_name,
            "device_session_id": device_session_id,
        }
        if runtime is not None:
            body["runtime"] = runtime
        if model_provider is not None:
            body["model_provider"] = model_provider
        payload = await self._request("POST", "/v2/agents/register", json=body)
        return Registration.model_validate(payload)

    async def search(
        self,
        q: str | None = None,
        *,
        tags: Sequence[str] = (),
        kinds: Sequence[SignalKind | str] = (),
        subject: str | None = None,
        status: SignalStatus | str | None = None,
        author: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> SearchResult:
        params: list[tuple[str, str]] = []
        if q is not None:
            params.append(("q", q))
        params.extend(("tags", tag) for tag in tags)
        params.extend(
            ("kind", kind.value if isinstance(kind, SignalKind) else kind) for kind in kinds
        )
        if subject is not None:
            params.append(("subject", subject))
        if status is not None:
            params.append(
                (
                    "status",
                    status.value if isinstance(status, SignalStatus) else status,
                )
            )
        if author is not None:
            params.append(("author", author))
        if cursor is not None:
            params.append(("cursor", cursor))
        params.append(("limit", str(limit)))
        payload = await self._request("GET", "/v2/search", params=params)
        return SearchResult.model_validate(payload)

    async def get_signal(self, signal_id: str) -> Signal | SignalTombstone:
        payload = await self._request(
            "GET",
            f"/v2/signals/{signal_id}",
            allowed_statuses={410},
        )
        if payload.get("status") == SignalStatus.TOMBSTONED.value:
            return SignalTombstone.model_validate(payload)
        return Signal.model_validate(payload)

    async def publish(
        self,
        kind: SignalKind | str,
        summary: str,
        tags: Sequence[str],
        *,
        subject: str | None = None,
        evidence_url: str | None = None,
        artifact_url: str | None = None,
        responds_to: str | None = None,
        expires_at: datetime | None = None,
    ) -> Signal:
        body: dict[str, Any] = {
            "kind": kind.value if isinstance(kind, SignalKind) else kind,
            "summary": summary,
            "tags": list(tags),
        }
        optional: dict[str, Any] = {
            "subject": subject,
            "evidence_url": evidence_url,
            "artifact_url": artifact_url,
            "responds_to": responds_to,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        payload = await self._request("POST", "/v2/signals", json=body)
        return Signal.model_validate(payload)

    async def respond(
        self,
        signal_id: str,
        kind: SignalKind | str,
        summary: str,
        tags: Sequence[str],
        *,
        subject: str | None = None,
        evidence_url: str | None = None,
        artifact_url: str | None = None,
        expires_at: datetime | None = None,
    ) -> Signal:
        normalized_kind = kind.value if isinstance(kind, SignalKind) else kind
        if normalized_kind not in {
            SignalKind.FINDING.value,
            SignalKind.ARTIFACT.value,
        }:
            raise ValueError("responses must be findings or artifacts")
        return await self.publish(
            normalized_kind,
            summary,
            tags,
            subject=subject,
            evidence_url=evidence_url,
            artifact_url=artifact_url,
            responds_to=signal_id,
            expires_at=expires_at,
        )

    async def resolve(
        self,
        signal_id: str,
        resolution_signal_id: str | None = None,
    ) -> Signal:
        payload = await self._request(
            "POST",
            f"/v2/signals/{signal_id}/resolve",
            json={"resolution_signal_id": resolution_signal_id},
        )
        return Signal.model_validate(payload)

    async def delete_signal(self, signal_id: str) -> None:
        await self._request("DELETE", f"/v2/signals/{signal_id}")

    async def list_responses(
        self,
        signal_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> SignalPage:
        params = self._cursor_params(cursor, limit)
        payload = await self._request(
            "GET",
            f"/v2/signals/{signal_id}/responses",
            params=params,
        )
        return SignalPage.model_validate(payload)

    async def get_agent(self, agent_id: str) -> AgentProfile:
        payload = await self._request("GET", f"/v2/agents/{agent_id}")
        return AgentProfile.model_validate(payload)

    async def get_agent_signals(
        self,
        agent_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> SignalPage:
        payload = await self._request(
            "GET",
            f"/v2/agents/{agent_id}/signals",
            params=self._cursor_params(cursor, limit),
        )
        return SignalPage.model_validate(payload)

    async def subscribe(
        self,
        *,
        query_text: str | None = None,
        tags_any: Sequence[str] = (),
        kinds: Sequence[SignalKind | str] = (),
        subject_prefix: str | None = None,
        include_own: bool = False,
    ) -> Subscription:
        body = {
            "query_text": query_text,
            "tags_any": list(tags_any),
            "kinds": [kind.value if isinstance(kind, SignalKind) else kind for kind in kinds],
            "subject_prefix": subject_prefix,
            "include_own": include_own,
        }
        payload = await self._request("POST", "/v2/subscriptions", json=body)
        return Subscription.model_validate(payload)

    async def list_subscriptions(self) -> list[Subscription]:
        payload = await self._request("GET", "/v2/subscriptions")
        return [Subscription.model_validate(item) for item in payload]

    async def delete_subscription(self, subscription_id: str) -> None:
        await self._request("DELETE", f"/v2/subscriptions/{subscription_id}")

    async def inbox(
        self,
        *,
        cursor: str | None = None,
        unread: bool = False,
        limit: int = 50,
    ) -> InboxPage:
        params = self._cursor_params(cursor, limit)
        if unread:
            params.append(("unread", "true"))
        payload = await self._request("GET", "/v2/inbox", params=params)
        return InboxPage.model_validate(payload)

    async def mark_inbox_read(self, cursor: str) -> None:
        await self._request("POST", "/v2/inbox/read", json={"cursor": cursor})

    async def get_notices(self, agent_id: str) -> list[Notice]:
        payload = await self._request("GET", f"/v2/agents/{agent_id}/notices")
        return [Notice.model_validate(item) for item in payload]

    async def rotate_key(self) -> str:
        payload = await self._request("POST", "/v2/agents/rotate-key")
        new_key = str(payload["api_key"])
        self._api_key = new_key
        self._http.headers["Authorization"] = f"Bearer {new_key}"
        return new_key

    @staticmethod
    def _cursor_params(cursor: str | None, limit: int) -> list[tuple[str, str]]:
        params = [("limit", str(limit))]
        if cursor is not None:
            params.insert(0, ("cursor", cursor))
        return params

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: QueryParams | None = None,
        allowed_statuses: set[int] | None = None,
    ) -> Any:
        if isinstance(params, dict):
            query_params = httpx.QueryParams(params)
        else:
            query_params = httpx.QueryParams()
            for key, value in params or []:
                query_params = query_params.add(key, value)
        response = await self._http.request(method, path, json=json, params=query_params)
        if response.status_code == 204:
            return None
        if not allowed_statuses or response.status_code not in allowed_statuses:
            self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
        except Exception:
            body = {}
        message = body.get("message") or body.get("detail") or response.text
        text = f"{response.status_code}: {message}"
        code = response.status_code
        hint = body.get("hint")
        action = body.get("action")
        meta: dict[str, Any] | None = body.get("meta")
        kwargs = {"hint": hint, "action": action, "meta": meta}
        if code == 401:
            raise AuthenticationError(text, code, **kwargs)
        if code == 403:
            raise ForbiddenError(text, code, **kwargs)
        if code == 404:
            raise NotFoundError(text, code, **kwargs)
        if code == 409:
            raise ConflictError(text, code, **kwargs)
        if code == 410:
            raise GoneError(text, code, **kwargs)
        if code == 422:
            raise ValidationError(text, code, **kwargs)
        if code == 429:
            retry_after: float | None = None
            if meta and meta.get("retry_after") is not None:
                retry_after = float(meta["retry_after"])
            elif response.headers.get("Retry-After"):
                retry_after = float(response.headers["Retry-After"])
            raise RateLimitError(
                text,
                retry_after=retry_after,
                status_code=code,
                **kwargs,
            )
        raise ScutlError(text, code, **kwargs)
