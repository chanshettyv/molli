"""Shared retry policy for Vertex AI calls that can hit 429 Resource Exhausted.

One chat turn fans out to several Vertex calls (guardrail classifier, topic
detection, intent classification, follow-up rewrite, embedding, RAG
generation) that all draw from the same per-minute quota. A short, bounded
backoff absorbs a transient 429 by retrying within the same request instead
of surfacing FALLBACK_MESSAGE on the first blip.

Only applied to the RAG/generation/embedding/retrieval call sites, which have
no tight timeout wrapping them. The classifier helpers (llm_classifier,
topic_detection, intent, query_rewrite) are wrapped in asyncio.wait_for with
a 1.5-2s fail-open budget -- a retry there would usually just get cancelled
by that timeout before it could help, so they're left as-is.
"""

from __future__ import annotations

from google.api_core.exceptions import ResourceExhausted
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

vertex_retry = retry(
    retry=retry_if_exception_type(ResourceExhausted),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
