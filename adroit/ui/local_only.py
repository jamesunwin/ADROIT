"""The workbench answers only its own pages on this machine (the audit loop's AL3-10, 2026-11-15).

The app listens on 127.0.0.1, but a page of another site open in the same browser can still reach it: through a name
of its own made to resolve to 127.0.0.1 (DNS rebinding), or by a request the browser sends with that site's Origin.
NiceGUI checks neither, and its socket handshake answered such an Origin with an allowance and a session. This guard
sits in front of every request, page, file and socket alike, and refuses one whose Host is not this server's own (a
name of this machine at its port) or whose Origin, where the browser sends one, is not this server's (the classic
page's rule, ``workbench.server``, AL2-12).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

LOCAL_NAMES = ("127.0.0.1", "localhost", "[::1]")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


def foreign(scope: Scope) -> str:
    """Why this server will not answer the request, or "": its Host must be a name of this machine at the port the
    server listens on, and its Origin, where one is sent, this server's own."""
    headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
    server = scope.get("server")
    port = server[1] if server else None
    own = {f"{name}:{port}" for name in LOCAL_NAMES} if port is not None else set()
    if headers.get("host", "") not in own:
        return "this workbench answers only requests addressed to it on this machine"
    origin = headers.get("origin")
    if origin is not None and origin not in {f"http://{host}" for host in own}:
        return "this workbench answers only its own pages"
    return ""


class LocalOnly:
    """ASGI middleware: ``foreign`` requests are refused (403 for a page or file; a socket closed before it opens)."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        why = foreign(scope) if scope.get("type") in ("http", "websocket") else ""
        if not why:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await receive()                                  # the connection request, answered by a refusal
            await send({"type": "websocket.close", "code": 1008, "reason": why})
            return
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": why.encode()})
