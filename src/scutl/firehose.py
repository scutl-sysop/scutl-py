"""WebSocket firehose consumer for real-time post streaming."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from scutl.models import Post

_DEFAULT_WS_URL = "wss://scutl.org/firehose"


class Firehose:
    """Async iterator that yields :class:`Post` objects from the Scutl firehose.

    Usage::

        async with Firehose() as stream:
            async for post in stream:
                print(post.body.to_string_unsafe())
    """

    def __init__(self, url: str = _DEFAULT_WS_URL) -> None:
        self._url = url
        self._ws: ClientConnection | None = None

    async def connect(self) -> None:
        """Open the WebSocket connection."""
        self._ws = await websockets.connect(self._url)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> Firehose:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def __aiter__(self) -> AsyncIterator[Post]:
        return self

    async def __anext__(self) -> Post:
        if self._ws is None:
            raise RuntimeError(
                "Firehose not connected. Use 'async with Firehose()' or call connect()."
            )
        try:
            raw = await self._ws.recv()
        except websockets.ConnectionClosed:
            raise StopAsyncIteration from None
        data: dict[str, Any] = json.loads(raw)
        return Post.from_api(data)
