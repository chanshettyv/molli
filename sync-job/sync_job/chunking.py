"""Content normalization and chunking.

Document360 returns article bodies as HTML in the ``html_content`` field. This
module strips the HTML to clean text and splits it into chunks suitable for
embedding.

Chunking strategy (intentionally simple for the first version):
  - Split on heading boundaries (<h1>..<h6>) so each chunk stays topically
    coherent and can carry the heading as context.
  - Within a section, accumulate paragraphs up to a target token budget,
    then start a new chunk.
  - Token counting is approximate (chars / 4) to avoid a tokenizer dependency.
    text-embedding-004 accepts up to 2048 tokens per input; we target far less
    so each chunk is a focused retrieval unit.

This is deliberately replaceable — a smarter semantic chunker can swap in later
without touching the rest of the pipeline, as long as it returns list[Chunk].
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# Target chunk size in approximate tokens. ~500-1000 was the task guidance;
# 750 chars*4 ≈ 3000 chars is a reasonable middle. Tune after seeing real data.
_TARGET_TOKENS = 750
_CHARS_PER_TOKEN = 4
_TARGET_CHARS = _TARGET_TOKENS * _CHARS_PER_TOKEN

_BLOCK_TAGS = {"p", "div", "li", "tr", "blockquote", "pre"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class Chunk:
    """One embeddable unit of an article, with provenance for citation."""

    text: str
    heading: str  # nearest preceding heading, "" if none
    ordinal: int  # 0-based position within the article


class _TextExtractor(HTMLParser):
    """Collect text segments and heading markers from HTML.

    Emits a flat list of ("heading"|"text", content) tuples so the chunker can
    reconstruct sections without a full DOM.
    """

    def __init__(self) -> None:
        super().__init__()
        self.segments: list[tuple[str, str]] = []
        self._buf: list[str] = []
        self._current_heading_tag: str | None = None
        self._skip_depth = 0  # inside <script>/<style>

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in _HEADING_TAGS:
            self._flush_text()
            self._current_heading_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _HEADING_TAGS:
            heading_text = "".join(self._buf).strip()
            self._buf.clear()
            self._current_heading_tag = None
            if heading_text:
                self.segments.append(("heading", heading_text))
        elif tag in _BLOCK_TAGS:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._buf.append(data)

    def _flush_text(self) -> None:
        text = "".join(self._buf).strip()
        self._buf.clear()
        if text and self._current_heading_tag is None:
            self.segments.append(("text", text))


def html_to_segments(html: str) -> list[tuple[str, str]]:
    """Parse HTML into an ordered list of heading/text segments."""
    parser = _TextExtractor()
    parser.feed(html or "")
    parser._flush_text()
    return parser.segments


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_html(html: str) -> list[Chunk]:
    """Convert an article's HTML body into embeddable chunks.

    Idempotent and deterministic: the same HTML always yields the same chunks
    in the same order, so re-running the sync produces stable datapoint ids.
    """
    segments = html_to_segments(html)
    chunks: list[Chunk] = []
    current_heading = ""
    buffer: list[str] = []
    buffer_len = 0
    ordinal = 0

    def flush() -> None:
        nonlocal buffer, buffer_len, ordinal
        if not buffer:
            return
        text = _normalize_whitespace(" ".join(buffer))
        if text:
            chunks.append(Chunk(text=text, heading=current_heading, ordinal=ordinal))
            ordinal += 1
        buffer = []
        buffer_len = 0

    for kind, content in segments:
        if kind == "heading":
            flush()
            current_heading = _normalize_whitespace(content)
            continue
        piece = _normalize_whitespace(content)
        if not piece:
            continue
        # If a single block already exceeds the budget, split it hard.
        if len(piece) > _TARGET_CHARS:
            flush()
            for i in range(0, len(piece), _TARGET_CHARS):
                sub = piece[i : i + _TARGET_CHARS]
                chunks.append(Chunk(text=sub, heading=current_heading, ordinal=ordinal))
                ordinal += 1
            continue
        if buffer_len + len(piece) > _TARGET_CHARS:
            flush()
        buffer.append(piece)
        buffer_len += len(piece)

    flush()
    return chunks
