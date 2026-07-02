"""Convert Gemini's Markdown output into the limited HTML subset that
Google Chat's ``textParagraph`` widget renders.

Chat cards do NOT render Markdown and do NOT use the ``*bold*`` plain-text
syntax. ``textParagraph`` accepts a small HTML subset:
    <b> <i> <u> <s> <a href="..."> <br> <font color="...">

Anything outside that subset (headers, tables, images, nested lists) has no
native equivalent, so we degrade it sensibly: headers become bold lines,
list items get a leading bullet, tables are left mostly intact as text.

This is intentionally a pragmatic regex pass, not a real Markdown parser.
Gemini's output is well-behaved enough that a full parser (e.g. ``markdown``
+ a sanitizer) would be more dependency and surface area than the job needs.
If Molli ever needs faithful tables or nested structure, that's the signal to
switch to multiple card widgets (decoratedText, columns) rather than to grow
this function.
"""

from __future__ import annotations

import html
import re

__all__ = ["md_to_chat_html"]


def _escape_keep_tags(text: str) -> str:
    """Escape raw HTML special chars so user/LLM content can't inject markup.

    We escape everything first, then re-introduce our own safe tags in the
    conversion steps below. This means a literal ``<script>`` in the answer
    is shown as text, never rendered.
    """
    return html.escape(text, quote=False)


def md_to_chat_html(text: str) -> str:
    """Convert a Markdown string to Chat-card-renderable HTML.

    The output is safe to drop into a ``textParagraph`` ``text`` field.
    """
    if not text:
        return ""

    # 1. Escape first. Everything after this re-adds only the tags we control.
    out = _escape_keep_tags(text)

    # 2. Fenced code blocks ```...``` -> <font>...</font> on its own lines.
    #    Chat has no real code block in textParagraph; monospace isn't
    #    available either, so we wrap in <i> as a weak visual cue and keep
    #    line breaks. (If real code display matters, use a decoratedText
    #    widget later.) Captured content is already escaped.
    def _code_block(m: re.Match[str]) -> str:
        body = m.group(1).strip("\n")
        body = body.replace("\n", "<br>")
        return f"<i>{body}</i>"

    out = re.sub(r"```[a-zA-Z0-9_+-]*\n?(.*?)```", _code_block, out, flags=re.DOTALL)

    # 3. Inline code `x` -> <i>x</i>  (no monospace in Chat; italic is the
    #    least-bad cue). Done before bold/italic so backtick content is
    #    not re-processed.
    out = re.sub(r"`([^`]+)`", r"<i>\1</i>", out)

    # 4. Links [label](url) -> <a href="url">label</a>
    #    URL is validated loosely; only http(s) and mailto are allowed so a
    #    crafted answer can't emit javascript: links.
    def _link(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2).strip()
        if not re.match(r"^(https?://|mailto:)", url, flags=re.IGNORECASE):
            # Not a scheme we trust: render as plain text instead of a link.
            return f"{label} ({url})"
        # url was escaped earlier; &amp; inside query strings is fine in href.
        return f'<a href="{url}">{label}</a>'

    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, out)

    # 5. Bold **x** or __x__ -> <b>x</b>   (before single-char italic).
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"__([^_]+)__", r"<b>\1</b>", out)

    # 6. Italic *x* or _x_ -> <i>x</i>
    #    Single-underscore italics only between word boundaries to avoid
    #    mangling snake_case identifiers (my_var stays my_var).
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", out)
    out = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<i>\1</i>", out)

    # 7. Strikethrough ~~x~~ -> <s>x</s>
    out = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", out)

    # 8. Headers (#..######) at line start -> bold line.
    out = re.sub(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", r"<b>\1</b>", out)

    # 9. List items: -, *, + or "1." at line start -> bullet.
    #    Preserve leading indentation as non-breaking spaces so nested
    #    lists keep some shape.
    def _bullet(m: re.Match[str]) -> str:
        indent = m.group(1)
        pad = "&nbsp;&nbsp;" * (len(indent) // 2)
        return f"{pad}• {m.group(2)}"

    out = re.sub(r"(?m)^([ \t]*)[-*+]\s+(.+)$", _bullet, out)
    out = re.sub(r"(?m)^([ \t]*)\d+\.\s+(.+)$", _bullet, out)

    # 10. Horizontal rules --- / *** -> a thin separator line.
    out = re.sub(r"(?m)^\s*([-*_])\1{2,}\s*$", "──────────", out)

    # 11. Collapse 3+ newlines, then turn newlines into <br>. Chat renders
    #     literal \n in textParagraph, but <br> is explicit and survives
    #     JSON round-trips predictably.
    out = re.sub(r"\n{3,}", "\n\n", out).strip()

    return out.replace("\n", "<br>")
