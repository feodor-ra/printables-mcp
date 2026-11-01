"""Tests for the MCP tools, driven through an in-memory MCP client against the fake API."""

from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from conftest import FakeAPI, call, call_error, load
from mcp import Client

from printables_mcp import server

pytestmark = pytest.mark.anyio


def link_route(*, premium: str | None = None, broken: str | None = None) -> Callable[[dict[str, Any]], httpx2.Response]:
    """Answer ``GetDownloadLink``: a link per file, a premium refusal or a broken response for chosen IDs.

    Returns:
        The route handler.
    """

    def handler(body: dict[str, Any]) -> httpx2.Response:
        file_id = body["variables"]["id"]
        if file_id == broken:
            return httpx2.Response(400, text="<html>Bad Request</html>")
        if file_id == premium:
            return httpx2.Response(200, json=load("link_premium_error"))
        link = f"https://files.printables.com/{body['variables']['fileType']}/{file_id}"
        return httpx2.Response(200, json={"data": {"result": {"ok": True, "output": {"link": link, "ttl": 86400}}}})

    return handler


async def test_tools_are_listed_as_read_only(mcp_client: Client) -> None:
    """Every tool is registered with read-only hints and a structured output schema."""
    tools = (await mcp_client.list_tools()).tools
    assert [tool.name for tool in tools] == [tool.__name__ for tool in server.TOOLS]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True
        assert tool.output_schema is not None


async def test_search_models(mcp_client: Client, api: FakeAPI) -> None:
    """Search maps filters to API variables and returns normalised summaries."""
    api.reply("SearchModels", "search_benchy")
    result = await call(mcp_client, "search_models", query="benchy", limit=3, offset=6, price="free", has_makes=True)
    assert result["total"] == 3843
    assert result["offset"] == 6
    first = result["items"][0]
    assert first["id"] == "3161"
    assert first["url"] == "https://www.printables.com/model/3161-3d-benchy"
    assert first["author"]["url"] == "https://www.printables.com/@Prusa3D"
    assert first["category"]["path"] == "3D Printers / Test Models"
    assert first["rating"] == pytest.approx(4.94)
    assert first["is_free"]
    assert first["image_url"].startswith("https://media.printables.com/media/prints/3161/")
    assert api.calls("SearchModels") == [
        {"query": "benchy", "limit": 3, "offset": 6, "ordering": "best_match", "paid": "free", "hasMake": True}
    ]


async def test_search_models_defaults_send_no_filters(mcp_client: Client, api: FakeAPI) -> None:
    """Unset filters are not sent to the API at all."""
    api.reply("SearchModels", "search_benchy")
    await call(mcp_client, "search_models", query="benchy")
    assert api.calls("SearchModels") == [{"query": "benchy", "limit": 10, "offset": 0, "ordering": "best_match"}]


async def test_search_models_validates_arguments(mcp_client: Client) -> None:
    """Out-of-range arguments are rejected before any request."""
    message = await call_error(mcp_client, "search_models", query="benchy", limit=101)
    assert "limit" in message


async def test_paid_and_club_models(mcp_client: Client, api: FakeAPI) -> None:
    """Price and club flags are exposed; missing author, category and image come back as null."""
    paid = {"id": "1", "name": "Paid", "slug": "paid", "price": "5.00", "premium": False}
    club = {"id": "2", "name": "Club", "slug": "club", "price": None, "premium": True}
    api.reply("SearchModels", {"data": {"result": {"totalCount": 2, "items": [paid, club]}}})
    paid_item, club_item = (await call(mcp_client, "search_models", query="x"))["items"]
    assert (paid_item["is_free"], paid_item["price"], paid_item["club_only"]) == (False, 5.0, False)
    assert (club_item["is_free"], club_item["price"], club_item["club_only"]) == (False, None, True)
    assert paid_item["author"] is None
    assert paid_item["category"] is None
    assert paid_item["image_url"] is None


async def test_get_model(mcp_client: Client, api: FakeAPI) -> None:
    """The model card carries the Markdown description, license, print parameters and media."""
    api.reply("GetModel", "model_3161")
    model = await call(mcp_client, "get_model", model="https://www.printables.com/de/model/3161-3d-benchy")
    assert api.calls("GetModel") == [{"id": "3161"}]
    assert model["description"].startswith("### Update: [The Iconic 3DBenchy Enters the Public Domain](https://")
    assert model["license"] == {"id": "7", "name": "Creative Commons — Public Domain", "abbreviation": "CC0"}
    assert model["tags"] == ["boat", "test", "benchy", "testmodel"]
    assert model["materials"] == ["PLA"]
    assert model["printer"] == "Prusa MK3/S/S+"
    assert model["print_time_minutes"] == 148
    assert model["weight_grams"] == pytest.approx(29)
    assert model["authorship"] == "reupload"
    assert len(model["images"]) == 2
    assert model["pdf_url"].endswith(".pdf")
    assert model["remix_of"] == [{"model_id": None, "name": None, "url": "https://www.3dbenchy.com/"}]


async def test_get_model_remix_sources_link_to_printables(mcp_client: Client, api: FakeAPI) -> None:
    """A remix of a Printables model links to the parent's page."""
    api.reply("GetModel", "model_1202139")
    model = await call(mcp_client, "get_model", model="1202139")
    parent = {"model_id": "3161", "name": "3D BENCHY", "url": "https://www.printables.com/model/3161"}
    assert parent in model["remix_of"]


async def test_get_model_not_found(mcp_client: Client, api: FakeAPI) -> None:
    """A missing model is a tool error, not an empty result."""
    api.reply("GetModel", "model_missing")
    assert "Model 999999999 not found" in await call_error(mcp_client, "get_model", model="999999999")


async def test_get_model_invalid_reference(mcp_client: Client, api: FakeAPI) -> None:
    """An unparseable reference fails without touching the API."""
    assert "Not a Printables model ID or URL: 'benchy'" in await call_error(mcp_client, "get_model", model="benchy")
    assert not api.requests


async def test_api_errors_become_tool_errors(mcp_client: Client, api: FakeAPI) -> None:
    """API failures reach the model as readable tool errors."""
    api.reply("GetModel", {"errors": [{"message": "Cannot query field 'x'"}]}, status=400)
    assert "Printables API error: Cannot query field 'x'" in await call_error(mcp_client, "get_model", model="1")


async def test_list_model_files(mcp_client: Client, api: FakeAPI) -> None:
    """All file groups are listed in one request, with G-code slicing parameters and named ZIP packs."""
    api.reply("ModelFiles", "files_3161")
    result = await call(mcp_client, "list_model_files", model="3161")
    files = result["files"]
    assert [file["kind"] for file in files] == ["stl", "gcode", "gcode", "gcode", "gcode", "pack", "pack"]
    gcode = files[1]
    assert gcode == {
        "id": "240956",
        "kind": "gcode",
        "name": "BonkersBenchy_PLA_8m.bgcode",
        "size_bytes": 546849,
        "folder": "MK4S G-codes",
        "note": None,
        "preview_url": gcode["preview_url"],
        "printer": "Prusa MK4S",
        "material": "PLA",
        "print_time_minutes": 8,
        "layer_height_mm": 0.28,
        "nozzle_diameter_mm": 0.4,
        "weight_grams": 6.0,
    }
    assert files[0]["printer"] is None
    assert [file["name"] for file in files[5:]] == ["All model files (ZIP)", "All print files (ZIP)"]
    assert len(api.requests) == 1


async def test_list_model_files_includes_sla_and_other_files(mcp_client: Client, api: FakeAPI) -> None:
    """SLA files, other files and custom-named packs are listed too."""
    sla = {"id": "1", "name": "a.sl1", "fileSize": 10, "printDuration": "1.5", "layerHeight": "0.05"}
    other = {"id": "2", "name": "readme.pdf", "fileSize": 5, "note": " see this "}
    pack = {"id": "3", "name": "Custom pack", "fileSize": 15, "fileType": "OTHER_FILES"}
    model = {"id": "7", "slug": None, "slas": [sla], "otherFiles": [other], "downloadPacks": [pack]}
    api.reply("ModelFiles", {"data": {"model": model}})
    result = await call(mcp_client, "list_model_files", model="7")
    assert result["model_url"] == "https://www.printables.com/model/7"
    sla_file, other_file, pack_file = result["files"]
    assert (sla_file["kind"], sla_file["print_time_minutes"], sla_file["layer_height_mm"]) == ("sla", 90, 0.05)
    assert (other_file["kind"], other_file["note"]) == ("other", "see this")
    assert pack_file["name"] == "Custom pack"


async def test_get_download_links_for_all_files(mcp_client: Client, api: FakeAPI) -> None:
    """Without ``file_ids`` every file gets a link, in listing order, with the right file type."""
    api.reply("ModelFiles", "files_3161")
    api.handle("GetDownloadLink", link_route())
    links = (await call(mcp_client, "get_download_links", model="3161"))["links"]
    assert [link["file_id"] for link in links] == ["49068", "240956", "240957", "13745", "60999", "7763318", "7768534"]
    assert links[0] == {
        "file_id": "49068",
        "kind": "stl",
        "name": "3dbenchy.stl",
        "url": "https://files.printables.com/stl/49068",
        "expires_in_seconds": 86400,
        "error": None,
    }
    assert {variables["fileType"] for variables in api.calls("GetDownloadLink")} == {"stl", "gcode", "pack"}


async def test_get_download_links_for_selected_files(mcp_client: Client, api: FakeAPI) -> None:
    """Per-file failures are reported per file; duplicates are dropped and unknown IDs flagged."""
    api.reply("ModelFiles", "files_3161")
    api.handle("GetDownloadLink", link_route(premium="240956", broken="13745"))
    file_ids = ["7763318", "240956", "nope", "13745", "7763318"]
    links = (await call(mcp_client, "get_download_links", model="3161", file_ids=file_ids))["links"]
    by_id = {link["file_id"]: link for link in links}
    assert list(by_id) == ["7763318", "240956", "nope", "13745"]
    assert by_id["7763318"]["url"] == "https://files.printables.com/pack/7763318"
    assert by_id["240956"]["error"] == "cannot_download_premium_file_as_anonymous_user"
    assert by_id["240956"]["url"] is None
    assert by_id["nope"] == {
        "file_id": "nope",
        "kind": None,
        "name": None,
        "url": None,
        "expires_in_seconds": None,
        "error": "file_not_found",
    }
    assert "HTTP 400" in by_id["13745"]["error"]


async def test_get_download_links_without_reason(mcp_client: Client, api: FakeAPI) -> None:
    """A refusal without error messages still explains itself."""
    api.reply("ModelFiles", "files_3161")
    api.reply("GetDownloadLink", {"data": {"result": {"ok": False, "errors": None, "output": None}}})
    links = (await call(mcp_client, "get_download_links", model="3161", file_ids=["49068"]))["links"]
    assert links[0]["error"] == "no link returned"


async def test_get_download_links_for_missing_model(mcp_client: Client, api: FakeAPI) -> None:
    """Links for a missing model are a tool error."""
    api.reply("ModelFiles", "model_missing")
    assert "Model 5 not found" in await call_error(mcp_client, "get_download_links", model="5")


async def test_list_categories(mcp_client: Client, api: FakeAPI) -> None:
    """Categories come with their full path."""
    api.reply("ListCategories", "categories")
    categories = (await call(mcp_client, "list_categories"))["categories"]
    assert {"id": "12", "name": "Test Models", "path": "3D Printers / Test Models"} in categories


async def test_list_licenses(mcp_client: Client, api: FakeAPI) -> None:
    """Licenses come with IDs and abbreviations."""
    api.reply("ListLicenses", "licenses")
    licenses = (await call(mcp_client, "list_licenses"))["licenses"]
    assert licenses[0] == {"id": "7", "name": "Creative Commons — Public Domain", "abbreviation": "CC0"}


async def test_get_author(mcp_client: Client, api: FakeAPI) -> None:
    """A profile URL is looked up by handle."""
    api.reply("GetAuthor", "author_16")
    author = await call(mcp_client, "get_author", author="https://www.printables.com/@Prusa3D")
    assert api.calls("GetAuthor") == [{"id": "@Prusa3D"}]
    assert author["followers"] == 25243
    assert author["name"] == "Prusa Research"
    assert author["url"] == "https://www.printables.com/@Prusa3D"


async def test_get_author_falls_back_to_id_suffix(mcp_client: Client, api: FakeAPI) -> None:
    """A ``/@handle_16`` URL that is not a handle is retried by the numeric suffix."""
    author = load("author_16")

    def handler(body: dict[str, Any]) -> httpx2.Response:
        return httpx2.Response(200, json=author if body["variables"]["id"] == "16" else {"data": {"user": None}})

    api.handle("GetAuthor", handler)
    result = await call(mcp_client, "get_author", author="https://www.printables.com/@Prusa3D_16")
    assert result["id"] == "16"
    assert api.calls("GetAuthor") == [{"id": "@Prusa3D_16"}, {"id": "16"}]


async def test_get_author_not_found(mcp_client: Client, api: FakeAPI) -> None:
    """An unknown author is a tool error."""
    api.reply("GetAuthor", {"data": {"user": None}})
    assert "Author 'ghost' not found" in await call_error(mcp_client, "get_author", author="ghost")
    assert api.calls("GetAuthor") == [{"id": "@ghost"}]


async def test_list_author_models(mcp_client: Client, api: FakeAPI) -> None:
    """The author is resolved to an ID, the ordering is mapped, and a full page yields a cursor."""
    api.reply("GetAuthor", "author_16")
    api.reply("AuthorModels", "author_models_16")
    result = await call(mcp_client, "list_author_models", author="Prusa3D", ordering="most_downloaded", limit=2)
    assert [item["id"] for item in result["items"]] == ["3161", "25857"]
    assert result["next_cursor"]
    assert api.calls("AuthorModels") == [{"userId": "16", "limit": 2, "ordering": "-download_count"}]


async def test_list_author_models_last_page(mcp_client: Client, api: FakeAPI) -> None:
    """A short page has no next cursor; the given cursor is passed through."""
    api.reply("GetAuthor", "author_16")
    api.reply("AuthorModels", "author_models_16")
    result = await call(mcp_client, "list_author_models", author="16", limit=5, cursor="abc")
    assert result["next_cursor"] is None
    assert api.calls("AuthorModels") == [{"userId": "16", "limit": 5, "cursor": "abc", "ordering": "-date_published"}]


def test_main_runs_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """The console script serves over stdio."""
    transports: list[str] = []
    monkeypatch.setattr(server.MCPServer, "run", lambda _self, transport: transports.append(transport))
    server.main()
    assert transports == ["stdio"]
