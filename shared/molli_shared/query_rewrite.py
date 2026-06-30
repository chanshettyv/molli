"""Follow-up query rewriting for multi-turn retrieval.

"What about for Mac?" after a printer answer is meaningless as a standalone
retrieval query -- embedding it finds generic "Mac" chunks, not Mac-printer
chunks. This rewrites such follow-ups into self-contained queries USING the
prior turns, so retrieval embeds the right thing.

Mirrors the intent classifier conventions: temp-0 Gemini, _call_gemini named
for test patching, asyncio.to_thread + timeout, fail-SAFE (returns the
original query unchanged on any error/timeout/no-context). Rewriting is a
best-effort enhancement -- it must never make retrieval worse than the raw
query, and it must never block.

Cost note: only calls Gemini when prior context exists. First turn in a
session has nothing to rewrite against, so it returns immediately with no
call -- single-turn conversations pay nothing.
"""

from __future__ import annotations

import asyncio

import structlog
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

from molli_shared.config import get_settings

log = structlog.get_logger()

_REWRITE_TIMEOUT = 4.0

_SYSTEM_PROMPT = (
    "You rewrite a follow-up message into a standalone search query for a "
    "company knowledge base, using ONLY the conversation so far for context.\n"
    "Rules:\n"
    "1. If the latest message is already self-contained, return it UNCHANGED.\n"
    "2. If it's a follow-up (refers to something earlier, e.g. 'what about for "
    "Mac?', 'and on mobile?'), rewrite it into a full standalone question by "
    "pulling the missing subject from the prior turns.\n"
    "3. Use ONLY information present in the conversation. Do NOT invent topics, "
    "systems, or details that weren't mentioned.\n"
    "4. Return ONLY the rewritten query text -- no preamble, no quotes, no "
    "explanation."
)

_USER_TEMPLATE = (
    "Conversation so far:\n{history}\n\n"
    "Latest message: {query}\n\n"
    "Standalone search query:"
)


def _call_gemini(
    project_id: str, region: str, model_name: str, history: str, query: str
) -> str:
    """Synchronous Gemini call -- runs inside asyncio.to_thread."""
    vertexai.init(project=project_id, location=region)
    model = GenerativeModel(model_name=model_name, system_instruction=_SYSTEM_PROMPT)
    response = model.generate_content(
        _USER_TEMPLATE.format(history=history, query=query),
        generation_config=GenerationConfig(temperature=0.0),
    )
    return (response.text or "").strip()


async def rewrite_followup(query: str, history: str) -> str:
    """Rewrite a follow-up into a standalone query. Fail-safe to `query`.

    Returns the original query unchanged when there's no prior history (no
    Gemini call), or on any error/timeout. Never raises, never blocks.
    """
    if not query or not query.strip():
        return query
    if not history or not history.strip():
        return query  # first turn -- nothing to rewrite against, no call

    try:
        settings = get_settings()
    except Exception:
        return query
    if not settings.use_gemini:
        return query

    try:
        rewritten = await asyncio.wait_for(
            asyncio.to_thread(
                _call_gemini,
                settings.gcp_project_id,
                settings.gcp_region,
                settings.gemini_model,
                history,
                query,
            ),
            timeout=_REWRITE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("query_rewrite_timeout", query_len=len(query))
        return query
    except Exception as exc:  # noqa: BLE001
        log.error("query_rewrite_error", error=str(exc))
        return query

    rewritten = rewritten.strip()
    if not rewritten:
        return query
    if rewritten != query:
        log.info("query_rewritten", original=query, rewritten=rewritten)
    return rewritten
