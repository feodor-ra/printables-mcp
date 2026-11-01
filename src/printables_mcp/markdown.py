"""Conversion of model descriptions from the API's HTML to Markdown."""

from __future__ import annotations

import re

from markdownify import ATX, markdownify

from .refs import SITE_URL

_SITE_RELATIVE_TARGET = re.compile(r"\]\(/(?!/)")


def html_to_markdown(html: str | None) -> str:
    """Convert a description to Markdown, making site-relative links and images absolute.

    Args:
        html: Description HTML as returned by the API.

    Returns:
        Markdown text; empty when there is no description.
    """
    if html is None:
        return ""
    markdown = markdownify(html, heading_style=ATX, bullets="-").strip()
    return _SITE_RELATIVE_TARGET.sub(f"]({SITE_URL}/", markdown)
