"""Tests for ``html_to_markdown``."""

from printables_mcp.markdown import html_to_markdown


def test_empty() -> None:
    """A missing or empty description becomes an empty string."""
    assert not html_to_markdown(None)
    assert not html_to_markdown("")


def test_structure_is_preserved() -> None:
    """Headings, lists and emphasis survive the conversion."""
    html = "<h3>Print settings</h3><ul><li><strong>0.2 mm</strong> layers</li><li>no supports</li></ul>"
    assert html_to_markdown(html) == "### Print settings\n\n- **0.2 mm** layers\n- no supports"


def test_site_relative_targets_become_absolute() -> None:
    """Site-relative links and images point at printables.com; protocol-relative ones are kept."""
    html = (
        '<p><a href="/model/3161">Benchy</a> <img src="/media/a.png" alt="pic"> <a href="//cdn.example/x">cdn</a></p>'
    )
    assert html_to_markdown(html) == (
        "[Benchy](https://www.printables.com/model/3161) "
        "![pic](https://www.printables.com/media/a.png) [cdn](//cdn.example/x)"
    )
