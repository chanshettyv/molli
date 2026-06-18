"""Sync job entrypoint: Document360 -> chunk -> embed -> Vector Search.

Pipeline
--------
1. Read the watermark (Firestore). None => full sync (first run).
2. list_articles(modified_since=watermark) -> changed stubs.
3. get_articles(...) -> full bodies (bounded concurrency).
4. chunk each article's HTML body.
5. embed all chunks (text-embedding-004).
6. upsert into Vector Search with citation metadata.
7. write the new watermark (the time the run STARTED).

Idempotent: datapoint ids are {article_id}::{ordinal}, so re-running
overwrites rather than duplicates.

Run a full sync locally WITHOUT Firestore (first-run path):

    uv run python -m sync_job.main --skip-watermark

Once Firestore is provisioned, drop the flag for incremental runs.

Cloud Run job entrypoint is ``main()``; Cloud Scheduler triggers the job
on a daily cron (no HTTP server needed for a Cloud Run *job*).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime

from molli_shared.chunk_store import ChunkStore, StoredChunk
from molli_shared.clients.document360 import Article, Document360Client
from molli_shared.config import get_settings

from sync_job.chunking import chunk_html
from sync_job.embedding import Embedder
from sync_job.index_store import IndexedChunk, VectorIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync-job")

# The deployed index id + public endpoint domain aren't in the article schema;
# they come from the provisioning step. Endpoint domain is discoverable via
# `gcloud ai index-endpoints describe`. Kept here as the documented default for
# molli-dev; override via env if they change or for prod.
_DEPLOYED_INDEX_ID = "molli_knowledge_stream"
_PUBLIC_ENDPOINT_DOMAIN = "163164439.us-central1-719635778769.vdb.vertexai.goog"


async def _gather_articles(
    client: Document360Client,
    watermark: datetime | None,
    limit: int | None = None,
    retry_ids: list[str] | None = None,
) -> tuple[list[Article], list[str]]:
    stubs = await client.list_articles(modified_since=watermark)
    log.info("found %d changed/indexable article(s)", len(stubs))
    if limit is not None:
        stubs = stubs[:limit]
        log.info("limiting to first %d for this run", len(stubs))

    # Add previously-failed articles back into the fetch set. They are older
    # than the watermark (so list_articles excludes them), but they never got
    # indexed, so we retry them until they succeed. Build (id, lang) pairs;
    # for retried IDs we don't have a fresh stub, so default the language to en.
    seen_ids = {s.id for s in stubs}
    fetch_targets: list[tuple[str, str]] = [(s.id, s.language_code) for s in stubs]
    if retry_ids:
        added = 0
        for aid in retry_ids:
            if aid not in seen_ids:
                fetch_targets.append((aid, "en"))
                added += 1
        if added:
            log.info("retrying %d previously-failed article(s)", added)

    if not fetch_targets:
        return [], []

    # Fetch each article individually so one pathological article (e.g. a few
    # D360 IDs return 429 on every attempt regardless of rate — likely an
    # oversized or broken article server-side) can't crash the whole sync.
    # Failures are collected and reported; the run proceeds with what succeeded.
    articles = []
    failed: list[str] = []
    for aid, lang in fetch_targets:
        try:
            article = await client.get_article(aid, lang)
            articles.append(article)
        except Exception as exc:  # noqa: BLE001 — isolate per-article failure
            failed.append(aid)
            log.warning("skipping article %s after fetch failure: %s", aid, exc)
    if failed:
        log.warning(
            "%d article(s) failed to fetch and were skipped: %s", len(failed), ", ".join(failed)
        )
    return articles, failed


def run_sync(skip_watermark: bool = False, limit: int | None = None) -> dict[str, int]:
    """Synchronous orchestrator. Returns a small summary dict for logging."""
    settings = get_settings()
    started_at = datetime.now(UTC)

    # 1. Watermark (optional for first run / no Firestore)
    watermark = None
    store = None
    retry_ids: list[str] = []
    if not skip_watermark:
        from sync_job.watermark import WatermarkStore

        store = WatermarkStore(settings.gcp_project_id, settings.firestore_database)
        watermark = store.read()
        retry_ids = store.read_failed()
    log.info("watermark: %s", watermark or "(none — full sync)")
    if retry_ids:
        log.info("%d article(s) queued for retry from a previous run", len(retry_ids))

    # 2 + 3. List changed articles and fetch bodies
    client = Document360Client.from_settings()

    async def _fetch() -> tuple[list[Article], list[str]]:
        async with client:
            return await _gather_articles(client, watermark, limit, retry_ids)

    articles, failed_fetches = asyncio.run(_fetch())
    if not articles:
        log.info("nothing to sync")
        if store is not None:
            store.write(started_at)
            store.write_failed(failed_fetches)
        return {"articles": 0, "chunks": 0, "failed_fetches": len(failed_fetches)}

    # 4. Chunk every article, tracking provenance
    embedder = Embedder(settings.gcp_project_id, settings.gcp_region)
    chunk_store = ChunkStore(settings.gcp_project_id, settings.firestore_database)
    index = VectorIndex(
        project_id=settings.gcp_project_id,
        index_id=settings.vector_index_id,
        index_endpoint_id=settings.vector_index_endpoint,
        deployed_index_id=_DEPLOYED_INDEX_ID,
        public_endpoint_domain=_PUBLIC_ENDPOINT_DOMAIN,
        region=settings.gcp_region,
    )

    total_chunks = 0
    all_indexed: list[IndexedChunk] = []
    all_stored: list[StoredChunk] = []
    for article in articles:
        chunks = chunk_html(article.body)
        if not chunks:
            log.warning("article %s produced no chunks; skipping", article.id)
            continue

        # 5. Embed this article's chunks
        vectors = embedder.embed([c.text for c in chunks])

        # 6. Collect chunks with citation metadata (upsert happens in batches
        # below, NOT per-article — Vector Search has a per-minute stream-update
        # quota that per-article upserts blow through on a large sync).
        indexed = [
            IndexedChunk(
                article_id=article.id,
                ordinal=c.ordinal,
                vector=v,
                title=article.title,
                url=article.url or "",
                category_id=article.category_id or "",
                heading=c.heading,
            )
            for c, v in zip(chunks, vectors, strict=True)
        ]
        all_stored.extend(
            [
                StoredChunk(
                    datapoint_id=ic.datapoint_id,
                    text=c.text,
                    article_id=article.id,
                    title=article.title,
                    url=article.url or "",
                    heading=c.heading,
                    category_id=article.category_id or "",
                )
                for c, ic in zip(chunks, indexed, strict=True)
            ]
        )

        all_indexed.extend(indexed)
        total_chunks += len(indexed)
        log.info("article %s -> %d chunk(s)", article.id, len(indexed))

    # 6b. Batch-upsert everything, pausing between batches to stay under the
    # Matching Engine stream-update per-minute quota.
    log.info("upserting %d chunk(s) in batches", len(all_indexed))
    batch_size = 100
    for start in range(0, len(all_indexed), batch_size):
        batch = all_indexed[start : start + batch_size]
        index.upsert(batch)
        log.info("upserted %d / %d", min(start + batch_size, len(all_indexed)), len(all_indexed))
        if start + batch_size < len(all_indexed):
            time.sleep(6)  # ~100 datapoints / 6s keeps us well under quota

    # 6c. Persist chunk text to Firestore so chat-service can ground answers

    # on real content (Vector Search stores only vectors + metadata, not text).

    if all_stored:
        written = chunk_store.put_many(all_stored)

        log.info("wrote %d chunk(s) to the chunk store", written)

    # 7. Advance the watermark to the run start time, and persist the set of
    # articles that failed this run so the next run retries them (they're older
    # than the new watermark, so list_articles alone wouldn't pick them up).
    if store is not None:
        store.write(started_at)
        store.write_failed(failed_fetches)
        log.info("watermark advanced to %s", started_at.isoformat())
        if failed_fetches:
            log.info("%d failed article(s) queued for retry next run", len(failed_fetches))

    summary = {
        "articles": len(articles),
        "chunks": total_chunks,
        "failed_fetches": len(failed_fetches),
    }
    log.info("sync complete: %s", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Molli Document360 sync job")
    parser.add_argument(
        "--skip-watermark",
        action="store_true",
        help="Full sync without reading/writing Firestore (first-run / no Firestore).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only sync the first N articles (for testing against the rate limit).",
    )
    args = parser.parse_args()
    run_sync(skip_watermark=args.skip_watermark, limit=args.limit)


if __name__ == "__main__":
    main()
