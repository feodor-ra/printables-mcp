"""End-to-end checks against the real Printables API: ``uv run pytest -m live``."""

from collections.abc import AsyncGenerator

import httpx2
import pytest
from conftest import call
from mcp import Client

from printables_mcp.server import create_server

pytestmark = [pytest.mark.anyio, pytest.mark.live]

BENCHY = "3161"


@pytest.fixture
async def live_client() -> AsyncGenerator[Client]:
    """Connect an in-memory MCP client to a server talking to the real API.

    Yields:
        The connected client.
    """
    async with Client(create_server()) as client:
        yield client


async def test_search(live_client: Client) -> None:
    """Searching for benchy finds the 3DBenchy."""
    result = await call(live_client, "search_models", query="benchy", limit=5, price="free")
    assert result["total"] > 0
    assert any(item["id"] == BENCHY for item in result["items"])


async def test_model_card(live_client: Client) -> None:
    """The 3DBenchy card has a description and a license."""
    model = await call(live_client, "get_model", model=f"https://www.printables.com/model/{BENCHY}-3d-benchy")
    assert model["name"] == "3D BENCHY"
    assert model["description"]
    assert model["license"] is not None


async def test_files_and_download_link(live_client: Client) -> None:
    """An STL of the 3DBenchy gets a working download link."""
    files = (await call(live_client, "list_model_files", model=BENCHY))["files"]
    stl = next(file for file in files if file["kind"] == "stl")
    links = (await call(live_client, "get_download_links", model=BENCHY, file_ids=[stl["id"]]))["links"]
    assert links[0]["error"] is None
    async with httpx2.AsyncClient() as http:
        response = await http.head(links[0]["url"])
    assert response.status_code == 200


async def test_author(live_client: Client) -> None:
    """Prusa3D is found by handle and has paginated models."""
    author = await call(live_client, "get_author", author="@Prusa3D")
    models = await call(live_client, "list_author_models", author=author["id"], ordering="most_downloaded", limit=3)
    assert len(models["items"]) == 3
    assert models["next_cursor"]


async def test_reference_lists(live_client: Client) -> None:
    """Categories and licenses include known entries."""
    categories = (await call(live_client, "list_categories"))["categories"]
    licenses = (await call(live_client, "list_licenses"))["licenses"]
    assert any(category["id"] == "12" for category in categories)
    assert any(license_["abbreviation"] == "CC0" for license_ in licenses)
