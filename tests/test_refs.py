"""Tests for reference parsing and URL building."""

import pytest

from printables_mcp.refs import (
    InvalidReferenceError,
    author_url,
    media_url,
    model_url,
    parse_author_ref,
    parse_model_id,
)


@pytest.mark.parametrize(
    "ref",
    [
        3161,
        "3161",
        " 3161 ",
        "3161-3d-benchy",
        "https://www.printables.com/model/3161-3d-benchy",
        "https://www.printables.com/model/3161-3d-benchy/files",
        "https://www.printables.com/de/model/3161-3d-benchy",
        "https://www.printables.com/pt-br/model/3161",
        "printables.com/model/3161",
    ],
)
def test_parse_model_id(ref: str | int) -> None:
    """IDs, slugs and model URLs with or without a locale all yield the ID."""
    assert parse_model_id(ref) == "3161"


@pytest.mark.parametrize("ref", ["", "benchy", "https://www.printables.com/@Prusa3D", "3161 3d benchy"])
def test_parse_model_id_rejects_garbage(ref: str) -> None:
    """Anything that is not a model reference is rejected."""
    with pytest.raises(InvalidReferenceError, match="Not a Printables model ID or URL"):
        parse_model_id(ref)


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (16, "16"),
        ("16", "16"),
        ("Prusa3D", "@Prusa3D"),
        ("@Prusa3D", "@Prusa3D"),
        ("https://www.printables.com/@Prusa3D", "@Prusa3D"),
        ("https://www.printables.com/@Prusa3D_16/models", "@Prusa3D_16"),
        ("https://www.printables.com/fr/@Prusa3D", "@Prusa3D"),
    ],
)
def test_parse_author_ref(ref: str | int, expected: str) -> None:
    """Numeric IDs pass through; handles and profile URLs become ``@handle``."""
    assert parse_author_ref(ref) == expected


@pytest.mark.parametrize("ref", ["", "@", "two words"])
def test_parse_author_ref_rejects_garbage(ref: str) -> None:
    """Empty or malformed author references are rejected."""
    with pytest.raises(InvalidReferenceError, match="Not a Printables user ID"):
        parse_author_ref(ref)


def test_urls() -> None:
    """Page, profile and media URLs are built from API fields."""
    assert model_url("3161", "3d-benchy") == "https://www.printables.com/model/3161-3d-benchy"
    assert model_url("3161", None) == "https://www.printables.com/model/3161"
    assert author_url("Prusa3D") == "https://www.printables.com/@Prusa3D"
    assert media_url("media/x.png") == "https://media.printables.com/media/x.png"
    assert media_url(None) is None
    assert media_url("") is None
