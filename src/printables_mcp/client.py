"""Async client for the Printables GraphQL API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import anyio
import httpx2

from . import __version__

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self

API_URL = "https://api.printables.com/graphql/"
USER_AGENT = f"printables-mcp/{__version__} (+https://github.com/feodor-ra/printables-mcp)"

_RETRIES = 3
_SERVER_ERROR = 500

logger = logging.getLogger(__name__)


class PrintablesError(Exception):
    """The Printables API could not answer the request."""


class PrintablesClient:
    """Thin GraphQL client: one method, typed errors, retries on transient failures."""

    def __init__(
        self,
        transport: httpx2.AsyncBaseTransport | None = None,
        *,
        timeout: float = 20.0,
        backoff: float = 1.0,
    ) -> None:
        """Create the client.

        Args:
            transport: Custom transport (tests pass a mock one).
            timeout: Per-request timeout in seconds.
            backoff: Base delay in seconds between retries; attempt ``n`` waits ``n * backoff``.
        """
        self._backoff = backoff
        self._http = httpx2.AsyncClient(
            transport=transport,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )

    async def __aenter__(self) -> Self:
        """Enter the context, keeping the connection pool open.

        Returns:
            The client itself.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connection pool."""
        await self._http.aclose()

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a GraphQL document and return its ``data`` object.

        Args:
            query: The GraphQL document.
            variables: Variables for the document; ``None`` values are dropped.

        Returns:
            The ``data`` member of the response.

        Raises:
            PrintablesError: On network failure, a non-2xx status or GraphQL errors.
        """
        payload = {"query": query, "variables": {k: v for k, v in (variables or {}).items() if v is not None}}
        attempt = 1
        while True:
            try:
                response = await self._http.post(API_URL, json=payload)
            except httpx2.TransportError as exc:
                if attempt >= _RETRIES:
                    msg = f"Printables API is unreachable: {exc}"
                    raise PrintablesError(msg) from exc
                logger.warning("Printables request failed (attempt %d/%d): %s", attempt, _RETRIES, exc)
            else:
                if response.status_code < _SERVER_ERROR or attempt >= _RETRIES:
                    return _unwrap(response)
                logger.warning("Printables returned %d (attempt %d/%d)", response.status_code, attempt, _RETRIES)
            await anyio.sleep(self._backoff * attempt)
            attempt += 1


def _unwrap(response: httpx2.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("errors"):
        messages = "; ".join(str(error.get("message", error)) for error in body["errors"])
        msg = f"Printables API error: {messages}"
        raise PrintablesError(msg)
    if not response.is_success or not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        msg = f"Printables API returned an unexpected response (HTTP {response.status_code})"
        raise PrintablesError(msg)
    return body["data"]
