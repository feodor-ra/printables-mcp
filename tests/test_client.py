"""Tests for ``PrintablesClient``: payloads, error mapping and retries."""

import json

import httpx2
import pytest

from printables_mcp.client import API_URL, USER_AGENT, PrintablesClient, PrintablesError

pytestmark = pytest.mark.anyio


def playback(*responses: httpx2.Response | Exception) -> tuple[PrintablesClient, list[httpx2.Request]]:
    """Build a client whose transport plays back ``responses`` in order, without retry delays.

    Returns:
        The client and the list it records requests into.
    """
    seen: list[httpx2.Request] = []
    queue = list(responses)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return PrintablesClient(httpx2.MockTransport(handler), backoff=0), seen


async def test_returns_data_and_drops_null_variables() -> None:
    """The ``data`` object is returned; null variables are not sent; the User-Agent is honest."""
    client, seen = playback(httpx2.Response(200, json={"data": {"print": {"id": "1"}}}))
    async with client:
        data = await client.execute("query Q { print }", {"id": "1", "cursor": None})
    assert data == {"print": {"id": "1"}}
    request = seen[0]
    assert str(request.url) == API_URL
    assert request.headers["User-Agent"] == USER_AGENT
    assert json.loads(request.content) == {"query": "query Q { print }", "variables": {"id": "1"}}


async def test_graphql_errors_are_raised_even_with_http_400() -> None:
    """The API reports validation errors with HTTP 400; their messages are surfaced, not the status."""
    body = {"errors": [{"message": "Cannot query field 'x'"}, {"message": "second"}]}
    client, _ = playback(httpx2.Response(400, json=body))
    async with client:
        with pytest.raises(PrintablesError, match="Printables API error: Cannot query field 'x'; second"):
            await client.execute("query Q { x }")


async def test_graphql_errors_with_partial_data() -> None:
    """Errors win over partial data."""
    client, _ = playback(httpx2.Response(200, json={"errors": [{"message": "Invalid cursor"}], "data": None}))
    async with client:
        with pytest.raises(PrintablesError, match="Invalid cursor"):
            await client.execute("query Q { x }")


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(400, text="<html>Bad Request</html>"),
        httpx2.Response(200, json=["not", "an", "object"]),
        httpx2.Response(200, json={"data": None}),
        httpx2.Response(404, json={"data": {}}),
    ],
)
async def test_unexpected_responses(response: httpx2.Response) -> None:
    """Non-JSON bodies, malformed payloads and error statuses become a clear error."""
    client, _ = playback(response)
    async with client:
        with pytest.raises(PrintablesError, match=rf"unexpected response \(HTTP {response.status_code}\)"):
            await client.execute("query Q { x }")


async def test_retries_transient_failures() -> None:
    """Network errors and 5xx responses are retried."""
    client, seen = playback(
        httpx2.ConnectError("boom"),
        httpx2.Response(503, text="busy"),
        httpx2.Response(200, json={"data": {"ok": True}}),
    )
    async with client:
        assert await client.execute("query Q { ok }") == {"ok": True}
    assert len(seen) == 3


async def test_gives_up_after_repeated_network_errors() -> None:
    """After three network failures the error names the cause."""
    client, seen = playback(*(httpx2.ReadTimeout("slow") for _ in range(3)))
    async with client:
        with pytest.raises(PrintablesError, match="unreachable: slow"):
            await client.execute("query Q { x }")
    assert len(seen) == 3


async def test_gives_up_after_repeated_server_errors() -> None:
    """After three 5xx responses the last status is reported."""
    client, seen = playback(*(httpx2.Response(502, text="bad gateway") for _ in range(3)))
    async with client:
        with pytest.raises(PrintablesError, match=r"HTTP 502"):
            await client.execute("query Q { x }")
    assert len(seen) == 3
