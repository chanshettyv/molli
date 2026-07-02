"""Unit tests for the Markdown -> Chat HTML conversion, focused on how
source links render: plain hyperlinks, no citation numbering involved.
"""

from __future__ import annotations

from app.cards.text import md_to_chat_html


def test_markdown_link_becomes_anchor() -> None:
    out = md_to_chat_html("Reset your password from the [login page](https://x/y).")
    assert '<a href="https://x/y">login page</a>' in out


def test_untrusted_scheme_link_rendered_as_plain_text() -> None:
    out = md_to_chat_html("See [here](javascript:alert(1)) for details.")
    assert "<a" not in out
    assert "here" in out


def test_sources_footer_renders_as_bulleted_links() -> None:
    out = md_to_chat_html(
        "Here's how to reset your password.\n\nSources:\n- [Password Reset](https://x/y)"
    )
    assert '<a href="https://x/y">Password Reset</a>' in out
    assert "•" in out
    # No leftover bracketed numbering anywhere.
    assert "[1]" not in out
