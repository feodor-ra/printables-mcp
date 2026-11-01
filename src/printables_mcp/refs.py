"""Parsing of the model and author references an agent may pass in."""

from __future__ import annotations

import re

SITE_URL = "https://www.printables.com"
MEDIA_URL = "https://media.printables.com"

_MODEL_URL = re.compile(r"printables\.com/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?model/(\d+)", re.IGNORECASE)
_AUTHOR_URL = re.compile(r"printables\.com/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?@([\w.-]+)", re.IGNORECASE)
_MODEL_ID = re.compile(r"(\d+)(?:-[\w-]*)?")
_HANDLE = re.compile(r"@?([\w.-]+)")


class InvalidReferenceError(ValueError):
    """The reference is neither an ID nor a recognisable Printables URL."""


def parse_model_id(ref: str | int) -> str:
    """Extract a model ID from an ID or a model page URL.

    Args:
        ref: ``3161``, ``"3161"``, ``"3161-3d-benchy"`` or ``https://www.printables.com/model/3161-3d-benchy``
            (with or without a locale prefix such as ``/de/``).

    Returns:
        The numeric model ID as a string.

    Raises:
        InvalidReferenceError: If no model ID can be found.
    """
    text = str(ref).strip()
    match = _MODEL_URL.search(text) or _MODEL_ID.fullmatch(text)
    if match is not None:
        return str(match.group(1))
    msg = f"Not a Printables model ID or URL: {ref!r}"
    raise InvalidReferenceError(msg)


def parse_author_ref(ref: str | int) -> str:
    """Normalise an author reference to what the API accepts as a user ID.

    Args:
        ref: A numeric user ID, a handle (``Prusa3D`` or ``@Prusa3D``) or a profile URL
            (``https://www.printables.com/@Prusa3D``).

    Returns:
        The numeric ID, or ``@handle``.

    Raises:
        InvalidReferenceError: If the reference is empty or malformed.
    """
    text = str(ref).strip()
    if text.isdigit():
        return text
    match = _AUTHOR_URL.search(text) or _HANDLE.fullmatch(text)
    if match is not None:
        return f"@{match.group(1)}"
    msg = f"Not a Printables user ID, handle or profile URL: {ref!r}"
    raise InvalidReferenceError(msg)


def model_url(model_id: str, slug: str | None) -> str:
    """Build the public page URL of a model.

    Returns:
        The model page URL.
    """
    return f"{SITE_URL}/model/{model_id}-{slug}" if bool(slug) else f"{SITE_URL}/model/{model_id}"


def author_url(handle: str) -> str:
    """Build the public profile URL of an author.

    Returns:
        The profile URL.
    """
    return f"{SITE_URL}/@{handle}"


def media_url(file_path: str | None) -> str | None:
    """Turn a media ``filePath`` from the API into an absolute URL.

    Returns:
        The absolute URL, or ``None`` when there is no path.
    """
    return f"{MEDIA_URL}/{file_path}" if bool(file_path) else None
