"""The MCP server: tool definitions and the ``printables-mcp`` entry point."""

from __future__ import annotations

import logging
import re
import sys
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Annotated, Any, Literal

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, queries
from .client import PrintablesClient, PrintablesError
from .models import (
    AuthorModels,
    AuthorProfile,
    Categories,
    Category,
    DownloadLink,
    DownloadLinks,
    License,
    Licenses,
    ModelDetails,
    ModelFile,
    ModelFiles,
    ModelSummary,
    SearchResults,
)
from .refs import InvalidReferenceError, parse_author_ref, parse_model_id

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    import httpx2

INSTRUCTIONS = """\
Printables.com is a catalogue of 3D-printable models. Typical flow: `search_models` to find candidates,
`get_model` for the description, license and print parameters, `list_model_files` to see the files, then
`get_download_links` for direct URLs (valid for 24 hours). `list_categories` and `list_licenses` give the IDs
the search filters take. Models and authors can be referenced by ID or by their printables.com URL.\
"""

_DOWNLOAD_CONCURRENCY = 5
_PRICE_FILTER = {"all": None, "free": "free", "paid": "paid"}
_AUTHOR_ORDERING = {
    "newest": "-date_published",
    "oldest": "date_published",
    "most_liked": "-likes_count",
    "most_downloaded": "-download_count",
    "top_rated": "-rating_avg",
    "most_made": "-makes_count",
}

PrintablesContext = Context[PrintablesClient, Any]
ModelRef = Annotated[str, Field(description='Model ID ("3161") or model page URL')]
AuthorRef = Annotated[str, Field(description='User ID ("16"), handle ("Prusa3D" or "@Prusa3D") or profile URL')]
PageSize = Annotated[int, Field(ge=1, le=100)]


@contextmanager
def _tool_errors() -> Generator[None]:
    try:
        yield
    except (PrintablesError, InvalidReferenceError) as exc:
        raise ToolError(str(exc)) from exc


async def _fetch_model(ctx: PrintablesContext, query: str, ref: str) -> dict[str, Any]:
    model_id = parse_model_id(ref)
    model = (await ctx.request_context.lifespan_context.execute(query, {"id": model_id}))["model"]
    if model is None:
        msg = f"Model {model_id} not found"
        raise ToolError(msg)
    return model


async def _fetch_author(ctx: PrintablesContext, ref: str) -> dict[str, Any]:
    client = ctx.request_context.lifespan_context
    author_id = parse_author_ref(ref)
    user = (await client.execute(queries.GET_AUTHOR, {"id": author_id}))["user"]
    # Profile URLs may carry the numeric ID after the handle: /@Prusa3D_16.
    if user is None and (suffix := re.fullmatch(r"@.+_(\d+)", author_id)) is not None:
        user = (await client.execute(queries.GET_AUTHOR, {"id": suffix.group(1)}))["user"]
    if user is None:
        msg = f"Author {ref!r} not found"
        raise ToolError(msg)
    return user


async def _download_link(client: PrintablesClient, model_id: str, file: ModelFile) -> DownloadLink:
    link = DownloadLink(file_id=file.id, kind=file.kind, name=file.name, url=None, expires_in_seconds=None)
    variables = {"id": file.id, "modelId": model_id, "fileType": file.kind}
    try:
        result = (await client.execute(queries.GET_DOWNLOAD_LINK, variables))["result"]
    except PrintablesError as exc:
        return link.model_copy(update={"error": str(exc)})
    output = result.get("output") or {}
    if result.get("ok") and output.get("link"):
        return link.model_copy(update={"url": output["link"], "expires_in_seconds": output.get("ttl")})
    messages = [message for error in result.get("errors") or [] for message in error.get("messages") or []]
    return link.model_copy(update={"error": ", ".join(messages) or "no link returned"})


async def search_models(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
    ctx: PrintablesContext,
    query: Annotated[str, Field(description="Search text; empty string lists everything")],
    limit: PageSize = 10,
    offset: Annotated[int, Field(ge=0, description="Skip this many results (pagination)")] = 0,
    ordering: Literal["best_match", "popular", "latest", "rating", "makes_count"] = "best_match",
    category_id: Annotated[str | None, Field(description="Category ID from `list_categories`")] = None,
    price: Annotated[Literal["all", "free", "paid"], Field(description="paid includes club-only models")] = "all",
    license_ids: Annotated[list[str] | None, Field(description="License IDs from `list_licenses`")] = None,
    published_within_days: Annotated[int | None, Field(ge=1)] = None,
    has_makes: Annotated[bool | None, Field(description="Only models with user-posted prints")] = None,
) -> SearchResults:
    """Search Printables models by text with optional filters and pagination.

    Returns:
        The total match count and one page of model summaries.
    """
    variables = {
        "query": query,
        "limit": limit,
        "offset": offset,
        "ordering": ordering,
        "categoryId": category_id,
        "paid": _PRICE_FILTER[price],
        "licenses": license_ids,
        "publishedDateLimitDays": published_within_days,
        "hasMake": has_makes,
    }
    with _tool_errors():
        result = (await ctx.request_context.lifespan_context.execute(queries.SEARCH_MODELS, variables))["result"]
    items = [ModelSummary.from_api(item) for item in result["items"]]
    return SearchResults(total=result["totalCount"], offset=offset, items=items)


async def get_model(ctx: PrintablesContext, model: ModelRef) -> ModelDetails:
    """Get a model's full card: Markdown description, tags, category, license, print parameters, images, remixes.

    Returns:
        The model details.
    """
    with _tool_errors():
        return ModelDetails.from_api(await _fetch_model(ctx, queries.GET_MODEL, model))


async def list_model_files(ctx: PrintablesContext, model: ModelRef) -> ModelFiles:
    """List every downloadable file of a model with sizes and, for G-code, printer/material/slicing parameters.

    Use `get_download_links` to obtain the actual URLs.

    Returns:
        All files of the model.
    """
    with _tool_errors():
        return ModelFiles.from_api(await _fetch_model(ctx, queries.MODEL_FILES, model))


async def get_download_links(
    ctx: PrintablesContext,
    model: ModelRef,
    file_ids: Annotated[list[str] | None, Field(description="File IDs from `list_model_files`; omit for all")] = None,
) -> DownloadLinks:
    """Get direct download URLs (valid for 24 hours) for a model's files.

    Files that cannot be downloaded anonymously (paid or club-only models) come back with an `error` instead of a
    URL; the other files are unaffected.

    Returns:
        One link or error per requested file.
    """
    client = ctx.request_context.lifespan_context
    with _tool_errors():
        files = ModelFiles.from_api(await _fetch_model(ctx, queries.MODEL_FILES, model))
    if file_ids is None:
        targets: list[ModelFile | str] = list(files.files)
    else:
        targets = []
        for file_id in dict.fromkeys(file_ids):
            targets.extend([file for file in files.files if file.id == file_id] or [file_id])

    links: dict[int, DownloadLink] = {}
    limiter = anyio.Semaphore(_DOWNLOAD_CONCURRENCY)

    async def fetch(index: int, file: ModelFile) -> None:
        async with limiter:
            links[index] = await _download_link(client, files.model_id, file)

    async with anyio.create_task_group() as tg:
        for index, target in enumerate(targets):
            if isinstance(target, str):
                links[index] = DownloadLink(
                    file_id=target, kind=None, name=None, url=None, expires_in_seconds=None, error="file_not_found"
                )
            else:
                tg.start_soon(fetch, index, target)
    return DownloadLinks(model_id=files.model_id, links=[links[index] for index in sorted(links)])


async def list_categories(ctx: PrintablesContext) -> Categories:
    """List all model categories with their full paths; the IDs feed `search_models(category_id=...)`.

    Returns:
        All categories.
    """
    with _tool_errors():
        data = await ctx.request_context.lifespan_context.execute(queries.LIST_CATEGORIES)
    return Categories(categories=[Category.from_api(category) for category in data["categories"]])


async def list_licenses(ctx: PrintablesContext) -> Licenses:
    """List the licenses models are published under; the IDs feed `search_models(license_ids=...)`.

    Returns:
        All licenses.
    """
    with _tool_errors():
        data = await ctx.request_context.lifespan_context.execute(queries.LIST_LICENSES)
    return Licenses(licenses=[License.from_api(license_) for license_ in data["licenses"]])


async def get_author(ctx: PrintablesContext, author: AuthorRef) -> AuthorProfile:
    """Get an author's public profile.

    Returns:
        The profile.
    """
    with _tool_errors():
        return AuthorProfile.from_api(await _fetch_author(ctx, author))


async def list_author_models(
    ctx: PrintablesContext,
    author: AuthorRef,
    ordering: Literal["newest", "oldest", "most_liked", "most_downloaded", "top_rated", "most_made"] = "newest",
    limit: PageSize = 20,
    cursor: Annotated[str | None, Field(description="`next_cursor` from the previous page")] = None,
) -> AuthorModels:
    """List models published by an author, page by page.

    Returns:
        One page of the author's models and the cursor for the next one.
    """
    with _tool_errors():
        user = await _fetch_author(ctx, author)
        variables = {"userId": user["id"], "limit": limit, "cursor": cursor, "ordering": _AUTHOR_ORDERING[ordering]}
        result = (await ctx.request_context.lifespan_context.execute(queries.AUTHOR_MODELS, variables))["result"]
    items = [ModelSummary.from_api(item) for item in result["items"]]
    next_cursor = result.get("cursor") if len(items) == limit else None
    return AuthorModels(items=items, next_cursor=next_cursor or None)


TOOLS = (
    search_models,
    get_model,
    list_model_files,
    get_download_links,
    list_categories,
    list_licenses,
    get_author,
    list_author_models,
)


def create_server(transport: httpx2.AsyncBaseTransport | None = None) -> MCPServer[PrintablesClient]:
    """Build the server with all tools registered.

    Args:
        transport: HTTP transport for the Printables client (tests pass a mock one).

    Returns:
        The configured server.
    """

    @asynccontextmanager
    async def lifespan(_server: MCPServer[PrintablesClient]) -> AsyncGenerator[PrintablesClient]:
        async with PrintablesClient(transport) as client:
            yield client

    server = MCPServer("printables-mcp", version=__version__, instructions=INSTRUCTIONS, lifespan=lifespan)
    annotations = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)
    for tool in TOOLS:
        server.add_tool(tool, annotations=annotations)
    return server


def main() -> None:
    """Run the server over stdio (the ``printables-mcp`` command)."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    create_server().run(transport="stdio")
