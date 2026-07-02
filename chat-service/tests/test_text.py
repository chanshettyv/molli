"""Unit tests for the Markdown -> Chat HTML conversion, focused on the
citation-linkifying behaviour: inline [n] markers and Sources footer links.
"""

from __future__ import annotations

from app.cards.text import md_to_chat_html


def test_known_citation_marker_becomes_link() -> None:
    out = md_to_chat_html("Reset your password [1].", citation_urls={1: "https://x/y"})
    assert '<a href="https://x/y">[1]</a>' in out


def test_unknown_citation_marker_stays_literal() -> None:
    out = md_to_chat_html("See [9] for details.", citation_urls={1: "https://x/y"})
    assert "[9]" in out
    assert "<a" not in out


def test_footer_title_link_renders_as_anchor() -> None:
    out = md_to_chat_html("[1] [Password Reset](https://x/y)", citation_urls={1: "https://x/y"})
    assert '<a href="https://x/y">Password Reset</a>' in out


def test_non_http_scheme_citation_url_is_rejected() -> None:
    out = md_to_chat_html("See [1] for details.", citation_urls={1: "javascript:alert(1)"})
    assert "<a" not in out
    assert "[1]" in out


def test_no_citation_urls_leaves_markers_untouched() -> None:
    out = md_to_chat_html("See [1] for details.")
    assert out == "See [1] for details."
