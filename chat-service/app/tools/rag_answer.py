"""RAG answer pipeline: retrieve D360 chunks, ground Gemini on their text, cite.

This is the heart of Phase 1 and the kickoff DoD line:
"responses sourced directly from Document360 with citation links."

Flow:
    query -> embed (RETRIEVAL_QUERY) -> Vector Search top-k neighbour ids
          -> ChunkStore.get_many(ids) -> actual chunk text
          -> build grounded prompt with numbered sources (text + link)
          -> Gemini generates an answer citing sources inline as [1], [2]
          -> assemble a deduplicated citation list (title + D360 URL)

No-context handling: Vector Search always returns top-k neighbours even for an
off-topic query, so an empty result set is NOT a reliable "not covered" signal.
Instead the model is told to emit the exact token INSUFFICIENT_CONTEXT when the
retrieved sources don't actually answer the question; we detect that and set
no_context=True so the caller can fall back to a general answer.

Design choices:
- Answers ONLY from retrieved chunk text. No hallucinated Preiss policy.
- Uses settings.gemini_model (gemini-2.5-flash) -- NOT 1.5 Pro (not a valid
  Vertex model id; flash is also better for the <30s budget).
- Lazy init + broad error fallback (same pattern as gemini_client.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog
import vertexai
from molli_shared.chunk_store import ChunkStore, StoredChunk
from molli_shared.config import get_settings
from molli_shared.retrieval import Embedder, VectorIndex
from vertexai.generative_models import GenerationConfig, GenerativeModel

log = structlog.get_logger()

_DEPLOYED_INDEX_ID = "molli_knowledge_stream"
_PUBLIC_ENDPOINT_DOMAIN = "163164439.us-central1-719635778769.vdb.vertexai.goog"

_DEFAULT_TOP_K = 5
_MAX_CHARS_PER_CHUNK = 2000

# Sentinel the model emits when the retrieved sources don't answer the question.
_INSUFFICIENT = "INSUFFICIENT_CONTEXT"

RAG_SYSTEM_INSTRUCTION = (
    "You are Molli, Preiss's AI-powered employee assistant for IT, Operations, "
    "and HR questions. Answer using ONLY the numbered sources provided in the "
    "prompt. Rules:\n"
    "1. Base your answer only on the provided source text. Do not use outside "
    "knowledge about Preiss's internal systems, policies, or people.\n"
    "2. Cite sources inline with bracketed numbers like [1] or [2], right "
    "after the claim they support.\n"
    "3. If the provided sources do not actually answer the question, respond "
    "with EXACTLY the single token INSUFFICIENT_CONTEXT and nothing else -- no "
    "explanation, no apology, no citations. Do not fabricate.\n"
    "4. Be concise, friendly, professional. Prefer clear steps for how-tos.\n"
)

FALLBACK_MESSAGE = (
    "Sorry -- I'm having trouble answering that right now. Please try again in "
    "a moment, or submit a Freshservice ticket if it's urgent."
)

NO_CONTEXT_MESSAGE = (
    "I couldn't find anything in Preiss Central about that. You may want to "
    "submit a Freshservice ticket or check Preiss Central directly."
)


@dataclass
class Citation:
    number: int
    title: str
    url: str


@dataclass
class RagAnswer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    chunks_retrieved: int = 0
    no_context: bool = False

    def formatted(self) -> str:
        """Answer text with a Sources footer of working D360 links."""
        if not self.citations:
            return self.text
        lines = [self.text, "", "Sources:"]
        for c in self.citations:
            lines.append(f"[{c.number}] [{c.title}]({c.url})")
        return "\n".join(lines)


_model: GenerativeModel | None = None
_embedder: Embedder | None = None
_index: VectorIndex | None = None
_store: ChunkStore | None = None


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        settings = get_settings()
        vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
        _model = GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=RAG_SYSTEM_INSTRUCTION,
        )
    return _model


def _get_retrieval() -> tuple[Embedder, VectorIndex, ChunkStore]:
    global _embedder, _index, _store
    if _embedder is None or _index is None or _store is None:
        settings = get_settings()
        _embedder = Embedder(settings.gcp_project_id, settings.gcp_region)
        _index = VectorIndex(
            project_id=settings.gcp_project_id,
            index_id=settings.vector_index_id,
            index_endpoint_id=settings.vector_index_endpoint,
            deployed_index_id=_DEPLOYED_INDEX_ID,
            public_endpoint_domain=_PUBLIC_ENDPOINT_DOMAIN,
            region=settings.gcp_region,
        )
        _store = ChunkStore(settings.gcp_project_id, settings.firestore_database)
    return _embedder, _index, _store


def _build_prompt(
    query: str, ordered_ids: list[str], stored: dict[str, StoredChunk]
) -> tuple[str, list[Citation]]:
    """Render retrieved chunk text as numbered sources and build the prompt."""
    source_blocks: list[str] = []
    citations: list[Citation] = []
    seen_urls: set[str] = set()
    n = 0
    for dp_id in ordered_ids:
        ch = stored.get(dp_id)
        if ch is None or not ch.text.strip():
            continue
        n += 1
        label = f"{ch.title} -- {ch.heading}" if ch.heading else ch.title
        text = ch.text[:_MAX_CHARS_PER_CHUNK]
        source_blocks.append(f"[{n}] {label}\n{text}\nLink: {ch.url}")
        if ch.url and ch.url not in seen_urls:
            seen_urls.add(ch.url)
            citations.append(Citation(number=n, title=ch.title, url=ch.url))

    sources_text = "\n\n".join(source_blocks)
    prompt = (
        f"Employee question: {query}\n\n"
        f"Numbered sources from Preiss Central (Document360):\n\n"
        f"{sources_text}\n\n"
        f"Answer using only these sources, citing inline like [1]. If these "
        f"sources do not actually answer the question, reply with exactly "
        f"{_INSUFFICIENT} and nothing else."
    )
    return prompt, citations


def answer_with_citations(
    query: str, top_k: int = _DEFAULT_TOP_K, intent: str | None = None
) -> RagAnswer:
    """Retrieve, ground on chunk text, generate. Never raises.

    Sets no_context=True when retrieval is empty OR when the model judges the
    retrieved sources insufficient (emits the INSUFFICIENT_CONTEXT sentinel).
    """
    if not query.strip():
        return RagAnswer(text=NO_CONTEXT_MESSAGE, no_context=True)

    # intent is accepted for forward-compatibility: once a D360
    # category->department map exists, retrieval will soft-boost chunks whose
    # category matches the predicted department. Until then it is logged but
    # NOT applied -- retrieval stays unscoped so a wrong intent can't hide the
    # right answer. See docs/spikes/intent-classification.md.
    if intent:
        log.info("rag_intent_hint", intent=intent)

    try:
        embedder, index, store = _get_retrieval()
        vector = embedder.embed_query(query)
        neighbours = index.query(vector, neighbor_count=top_k)
    except Exception as exc:  # noqa: BLE001
        log.error("rag_retrieval_failed", error=str(exc))
        return RagAnswer(text=FALLBACK_MESSAGE)

    if not neighbours:
        log.info("rag_no_chunks", query=query)
        return RagAnswer(text=NO_CONTEXT_MESSAGE, no_context=True)

    ordered_ids = [n["id"] for n in neighbours]
    try:
        stored = store.get_many(ordered_ids)
    except Exception as exc:  # noqa: BLE001
        log.error("rag_chunk_store_failed", error=str(exc))
        return RagAnswer(text=FALLBACK_MESSAGE, chunks_retrieved=len(neighbours))

    if not stored:
        log.warning("rag_no_stored_text", ids=ordered_ids)
        return RagAnswer(text=NO_CONTEXT_MESSAGE, no_context=True, chunks_retrieved=len(neighbours))

    prompt, citations = _build_prompt(query, ordered_ids, stored)

    try:
        settings = get_settings()
        model = _get_model()
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=settings.gemini_temperature),
        )
        text = (response.text or "").strip()
        if not text:
            log.warning("rag_empty_response")
            return RagAnswer(text=FALLBACK_MESSAGE, chunks_retrieved=len(neighbours))
    except Exception as exc:  # noqa: BLE001
        log.error("rag_generation_failed", error=str(exc))
        return RagAnswer(text=FALLBACK_MESSAGE, chunks_retrieved=len(neighbours))

    # Model judged the retrieved sources insufficient -> signal no_context so
    # the caller can fall back to a general answer. Tolerate the sentinel
    # appearing alone or with stray punctuation/whitespace.
    if text.replace("*", "").strip().upper().startswith(_INSUFFICIENT):
        log.info("rag_insufficient_context", query=query)
        return RagAnswer(text=NO_CONTEXT_MESSAGE, no_context=True, chunks_retrieved=len(neighbours))

    cited = [c for c in citations if f"[{c.number}]" in text]
    final_citations = cited or citations
    return RagAnswer(
        text=text,
        citations=final_citations,
        chunks_retrieved=len(neighbours),
    )
