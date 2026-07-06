"""Manual PDF ingest into Molli's knowledge base (stopgap for PDFs not in D360).

Why this exists
---------------
The nightly sync job only knows about Document360 articles. When a PDF needs to
be answerable *before* it's been formatted into D360, this script ingests it
by hand into the same two stores the sync job writes:

    PDF text -> chunk -> embed (RETRIEVAL_DOCUMENT) -> Vector Search upsert
                                                    -> Firestore chunk store

Retrieval is source-agnostic: once a chunk lives in both the index and the
`chunks` collection under a matching datapoint id, `answer_with_citations`
grounds and cites it exactly like a real D360 article.

Datapoint id scheme
-------------------
article_id = ``pdf-manual::<slug>``  (stable, so re-runs overwrite, not
duplicate). datapoint id = ``pdf-manual::<slug>::<ordinal>``.

These datapoints live OUTSIDE the D360 watermark, so the nightly sync never
touches them -- they persist until you remove them here.

Migration cleanup
-----------------
When the same content is later published to D360 and picked up by the sync,
you MUST remove the manual copy or retrieval will hold two competing versions:

    python -m sync_job.manual_ingest remove --slug <slug>

Ownership note: this writes to the Vector Search index + chunk store, which are
Kautilya's lane. Validate on molli-dev first; give Kautilya a heads-up before
running against prod.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time

from google.cloud import firestore
from molli_shared.chunk_store import ChunkStore, StoredChunk
from molli_shared.config import get_settings
from molli_shared.retrieval import Embedder, IndexedChunk, VectorIndex
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("manual-ingest")

# Same deployed index + public endpoint the sync job and chat-service use.
# These are the documented molli-dev defaults; override via env for prod if the
# provisioning step produced different values (see sync_job/main.py).
_DEPLOYED_INDEX_ID = "molli_knowledge_stream"
_PUBLIC_ENDPOINT_DOMAIN = "163164439.us-central1-719635778769.vdb.vertexai.goog"

_CHUNK_COLLECTION = "chunks"
_ARTICLE_PREFIX = "pdf-manual"

# ~750 tokens per chunk, matching the sync job's target. Chunk on paragraph
# boundaries so we don't cut mid-sentence like a naive fixed-width split would.
_TARGET_CHARS = 3000

# Vector Search streaming upsert has a per-minute quota; mirror the sync job's
# pacing. For a single PDF this is almost always one batch (no pause).
_UPSERT_BATCH = 100
_UPSERT_PAUSE_S = 6


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise SystemExit("Could not derive a slug from the title; pass --slug explicitly.")
    return slug


def _extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(p for p in pages if p)
    if len(text) < 50:
        raise SystemExit(
            f"Extracted only {len(text)} chars from {path}. This PDF is likely "
            "scanned/image-only and needs OCR before it can be ingested."
        )
    log.info("extracted %d chars from %d page(s)", len(text), len(reader.pages))
    return text


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_long(piece: str) -> list[str]:
    """Split an over-budget paragraph on sentence boundaries, then hard-split
    anything still too long."""
    out: list[str] = []
    buf = ""
    for sentence in re.split(r"(?<=[.!?])\s+", piece):
        if len(buf) + len(sentence) + 1 > _TARGET_CHARS and buf:
            out.append(buf.strip())
            buf = ""
        if len(sentence) > _TARGET_CHARS:
            for i in range(0, len(sentence), _TARGET_CHARS):
                out.append(sentence[i : i + _TARGET_CHARS].strip())
            continue
        buf = f"{buf} {sentence}".strip()
    if buf:
        out.append(buf.strip())
    return [c for c in out if c]


def _chunk_text(text: str) -> list[str]:
    """Paragraph-aware chunker targeting ~_TARGET_CHARS per chunk.

    Deterministic: same input -> same chunks -> stable ordinals, so re-runs
    overwrite the same datapoint ids rather than duplicating.
    """
    paragraphs = [_normalize(p) for p in re.split(r"\n\s*\n", text) if _normalize(p)]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > _TARGET_CHARS:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_long(para))
            continue
        if buf and len(buf) + len(para) + 1 > _TARGET_CHARS:
            chunks.append(buf)
            buf = ""
        buf = f"{buf} {para}".strip()
    if buf:
        chunks.append(buf)
    return chunks


def _make_index(settings) -> VectorIndex:
    return VectorIndex(
        project_id=settings.gcp_project_id,
        index_id=settings.vector_index_id,
        index_endpoint_id=settings.vector_index_endpoint,
        deployed_index_id=_DEPLOYED_INDEX_ID,
        public_endpoint_domain=_PUBLIC_ENDPOINT_DOMAIN,
        region=settings.gcp_region,
    )


def ingest(pdf_path: str, title: str, url: str, slug: str, dry_run: bool) -> None:
    article_id = f"{_ARTICLE_PREFIX}::{slug}"
    text = _extract_pdf_text(pdf_path)
    chunk_texts = _chunk_text(text)
    if not chunk_texts:
        raise SystemExit("No chunks produced from the PDF; nothing to ingest.")
    log.info("article_id=%s -> %d chunk(s)", article_id, len(chunk_texts))

    if dry_run:
        for i, c in enumerate(chunk_texts):
            preview = c[:120].replace("\n", " ")
            log.info("  chunk %d (%d chars): %s...", i, len(c), preview)
        log.info("dry-run: no writes performed")
        return

    if not url:
        log.warning(
            "no --url given: chunks will ground answers but WON'T show in the "
            "Sources footer (citations need a url). Pass the Drive link."
        )

    settings = get_settings()
    embedder = Embedder(settings.gcp_project_id, settings.gcp_region)
    index = _make_index(settings)
    chunk_store = ChunkStore(settings.gcp_project_id, settings.firestore_database)

    vectors = embedder.embed(chunk_texts, title=title)

    indexed = [
        IndexedChunk(
            article_id=article_id,
            ordinal=i,
            vector=v,
            title=title,
            url=url,
            category_id="",
            heading="",
        )
        for i, v in enumerate(vectors)
    ]
    stored = [
        StoredChunk(
            datapoint_id=ic.datapoint_id,
            text=t,
            article_id=article_id,
            title=title,
            url=url,
            heading="",
            category_id="",
        )
        for ic, t in zip(indexed, chunk_texts, strict=True)
    ]

    log.info("upserting %d datapoint(s) to Vector Search", len(indexed))
    for start in range(0, len(indexed), _UPSERT_BATCH):
        batch = indexed[start : start + _UPSERT_BATCH]
        index.upsert(batch)
        log.info("upserted %d / %d", min(start + _UPSERT_BATCH, len(indexed)), len(indexed))
        if start + _UPSERT_BATCH < len(indexed):
            time.sleep(_UPSERT_PAUSE_S)

    written = chunk_store.put_many(stored)
    log.info("wrote %d chunk(s) to Firestore '%s'", written, _CHUNK_COLLECTION)
    log.info(
        "done. give the streaming upsert ~1 min to become queryable, then test "
        "a question this PDF answers on molli-dev before promoting to prod."
    )


def remove(slug: str) -> None:
    article_id = f"{_ARTICLE_PREFIX}::{slug}"
    settings = get_settings()

    # Index side: remove_article(article_id, 0) sweeps ordinals 0..49, which
    # covers any single-PDF ingest.
    index = _make_index(settings)
    index.remove_article(article_id, keep_ordinals=0)
    log.info("removed index datapoints for %s (ordinals 0-49)", article_id)

    # Firestore side: ChunkStore has no delete, so query the collection by
    # article_id and delete the matching docs directly.
    fs = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database)
    col = fs.collection(_CHUNK_COLLECTION)
    docs = list(col.where("article_id", "==", article_id).stream())
    deleted = 0
    batch = fs.batch()
    for i, doc in enumerate(docs, 1):
        batch.delete(doc.reference)
        if i % 450 == 0:
            batch.commit()
            batch = fs.batch()
        deleted += 1
    if deleted % 450 != 0:
        batch.commit()
    log.info("deleted %d chunk doc(s) from Firestore for %s", deleted, article_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual PDF ingest for Molli's knowledge base")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a PDF into the knowledge base")
    p_ingest.add_argument("--pdf", required=True, help="Path to the local PDF file")
    p_ingest.add_argument("--title", required=True, help="Title shown in citations")
    p_ingest.add_argument("--url", default="", help="Citation link (e.g. the Drive URL of the PDF)")
    p_ingest.add_argument(
        "--slug", default="", help="Override the slug (default: derived from title)"
    )
    p_ingest.add_argument("--dry-run", action="store_true", help="Extract + chunk only; no writes")

    p_remove = sub.add_parser("remove", help="Remove a previously ingested PDF (migration cleanup)")
    p_remove.add_argument("--slug", required=True, help="The slug used at ingest time")

    args = parser.parse_args()

    if args.command == "ingest":
        slug = args.slug or _slugify(args.title)
        ingest(args.pdf, args.title, args.url, slug, args.dry_run)
    elif args.command == "remove":
        remove(args.slug)
    else:  # pragma: no cover
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
