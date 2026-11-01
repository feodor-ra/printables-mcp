"""Shared fixtures: a fake Printables API built from recorded responses, and an in-memory MCP client."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.types import CallToolResult

from printables_mcp.server import create_server

FIXTURES = Path(__file__).parent / "fixtures"
_OPERATION = re.compile(r"(?:query|mutation)\s+(\w+)")

Handler = Callable[[dict[str, Any]], httpx2.Response]


def load(name: str) -> dict[str, Any]:
    """Read a recorded API response from ``tests/fixtures``.

    Returns:
        The parsed JSON body.
    """
    return json.loads((FIXTURES / f"{name}.json").read_text())


class FakeAPI:
    """Answers GraphQL operations by name and records every request body."""

    def __init__(self) -> None:
        """Start with no routes and no recorded requests."""
        self.routes: dict[str, Handler] = {}
        self.requests: list[dict[str, Any]] = []

    def reply(self, operation: str, body: dict[str, Any] | str, status: int = 200) -> None:
        """Answer ``operation`` with a fixture name or a literal body."""
        payload = load(body) if isinstance(body, str) else body
        self.routes[operation] = lambda _request: httpx2.Response(status, json=payload)

    def handle(self, operation: str, handler: Handler) -> None:
        """Answer ``operation`` with a custom handler receiving the request body."""
        self.routes[operation] = handler

    def calls(self, operation: str) -> list[dict[str, Any]]:
        """Return the variables of every request made for ``operation``."""
        return [request["variables"] for request in self.requests if _operation(request) == operation]

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        """Serve a request as an ``httpx2.MockTransport`` handler.

        Returns:
            The routed response.
        """
        body = json.loads(request.content)
        self.requests.append(body)
        return self.routes[_operation(body)](body)


def _operation(body: dict[str, Any]) -> str:
    match = _OPERATION.search(body["query"])
    assert match is not None
    return str(match.group(1))


async def call(client: Client, tool: str, **arguments: object) -> dict[str, Any]:
    """Call a tool that must succeed.

    Returns:
        Its structured result.
    """
    result = await client.call_tool(tool, arguments)
    assert isinstance(result, CallToolResult)
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return result.structured_content


async def call_error(client: Client, tool: str, **arguments: object) -> str:
    """Call a tool that must fail.

    Returns:
        The error text shown to the model.
    """
    result = await client.call_tool(tool, arguments)
    assert isinstance(result, CallToolResult)
    assert result.is_error
    text = result.content[0]
    assert text.type == "text"
    return text.text


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only.

    Returns:
        The anyio backend name.
    """
    return "asyncio"


@pytest.fixture
def api() -> FakeAPI:
    """Provide a fresh fake API per test.

    Returns:
        The fake API.
    """
    return FakeAPI()


@pytest.fixture
async def mcp_client(api: FakeAPI) -> AsyncGenerator[Client]:
    """Connect an in-memory MCP client to a server backed by the fake API.

    Yields:
        The connected client.
    """
    async with Client(create_server(httpx2.MockTransport(api))) as client:
        yield client
