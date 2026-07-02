"""Smoke tests for the RAG answer pipeline.

These run WITHOUT live GCP — the embed/retrieve/generate calls are not
exercised here (that's the latency harness, run manually). We test the pure
logic that doesn't need cloud: citation assembly, prompt building, the
no-context path, and the formatted() output. Live retrieval quality is
validated by scripts/spikes/rag_retrieval_check and the latency harness.
"""

from __future__ import annotations

from app.tools.rag_answer import (
    Citation,
    RagAnswer,
    _build_prompt,
    answer_with_citations,
)
from molli_shared.chunk_store import StoredChunk


def test_formatted_appends_sources() -> None:
    ans = RagAnswer(
        text="Reset your password from the login page [1].",
        citations=[Citation(number=1, title="Password Reset", url="https://x/y")],
        chunks_retrieved=1,
    )
    out = ans.formatted()
    assert "Reset your password" in out
    assert "Sources:" in out
    assert "https://x/y" in out
    assert "[1] [Password Reset](https://x/y)" in out


def test_formatted_no_citations_is_plain() -> None:
    ans = RagAnswer(text="I don't have that.", citations=[])
    assert ans.formatted() == "I don't have that."


def test_build_prompt_numbers_sources_and_dedupes_urls() -> None:
    ordered_ids = ["a::0", "a::1", "b::0"]
    stored = {
        "a::0": StoredChunk("a::0", "First chunk text.", "a", "Article A", "https://x/a", "Intro"),
        "a::1": StoredChunk(
            "a::1", "Second chunk text.", "a", "Article A", "https://x/a", "Details"
        ),
        "b::0": StoredChunk("b::0", "Other article text.", "b", "Article B", "https://x/b", ""),
    }
    prompt, citations = _build_prompt("how do I X?", ordered_ids, stored)
    # All three chunks numbered in the prompt
    assert "[1]" in prompt and "[2]" in prompt and "[3]" in prompt
    assert "First chunk text." in prompt
    # Citations dedupe by URL: Article A (cited twice) appears once
    urls = [c.url for c in citations]
    assert urls.count("https://x/a") == 1
    assert "https://x/b" in urls


def test_build_prompt_skips_missing_or_empty_chunks() -> None:
    ordered_ids = ["a::0", "missing::9", "b::0"]
    stored = {
        "a::0": StoredChunk("a::0", "Real text.", "a", "A", "https://x/a", ""),
        "b::0": StoredChunk("b::0", "   ", "b", "B", "https://x/b", ""),  # empty
    }
    prompt, citations = _build_prompt("q", ordered_ids, stored)
    # Only the one non-empty, present chunk should be numbered [1]
    assert "[1]" in prompt
    assert "[2]" not in prompt
    assert len(citations) == 1


def test_empty_query_returns_no_context() -> None:
    ans = answer_with_citations("   ")
    assert ans.no_context is True
    assert ans.citations == []
