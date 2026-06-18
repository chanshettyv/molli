"""Firestore-backed store for chunk text, keyed by Vector Search datapoint id.

Vector Search datapoints hold a vector + short `restricts` metadata tokens --
they are not meant to carry document bodies. So we keep the chunk *text* here,
in Firestore, keyed by the same datapoint id (`{article_id}::{ordinal}`) the
index uses. RAG flow:

    query -> Vector Search returns neighbour ids
          -> ChunkStore.get_many(ids) returns the text for those ids
          -> text grounds the Gemini answer

Collection: `chunks`. Document id = datapoint id. Fields:
    text, article_id, title, url, heading, category_id

Written by the sync job during indexing; read by chat-service at query time.
A batch read of ~5 ids is fast (tens of ms), so this does not threaten the
<30s first-response budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.cloud import firestore

_COLLECTION = "chunks"


@dataclass
class StoredChunk:
    """A chunk's text plus the metadata needed to cite it."""

    datapoint_id: str
    text: str
    article_id: str
    title: str
    url: str
    heading: str
    category_id: str = ""


class ChunkStore:
    """Read/write chunk text in Firestore, keyed by datapoint id."""

    def __init__(self, project_id: str, database: str = "(default)") -> None:
        self._client = firestore.Client(project=project_id, database=database)
        self._col = self._client.collection(_COLLECTION)

    def put_many(self, chunks: list[StoredChunk]) -> int:
        """Upsert chunks in batches (Firestore caps at 500 writes/batch).

        Idempotent: doc id is the datapoint id, so re-indexing overwrites the
        same docs rather than duplicating (mirrors the Vector Search upsert).
        """
        written = 0
        batch = self._client.batch()
        pending = 0
        for ch in chunks:
            ref = self._col.document(ch.datapoint_id)
            batch.set(
                ref,
                {
                    "text": ch.text,
                    "article_id": ch.article_id,
                    "title": ch.title,
                    "url": ch.url,
                    "heading": ch.heading,
                    "category_id": ch.category_id,
                },
            )
            pending += 1
            if pending >= 450:
                batch.commit()
                written += pending
                batch = self._client.batch()
                pending = 0
        if pending:
            batch.commit()
            written += pending
        return written

    def get_many(self, datapoint_ids: list[str]) -> dict[str, StoredChunk]:
        """Fetch chunk text for a list of datapoint ids in one round trip.

        Returns a dict keyed by datapoint id; ids with no stored doc are
        omitted (caller decides how to handle a miss).
        """
        if not datapoint_ids:
            return {}
        refs = [self._col.document(i) for i in datapoint_ids]
        out: dict[str, StoredChunk] = {}
        for snap in self._client.get_all(refs):
            if not snap.exists:
                continue
            d = snap.to_dict()
            if d is None:
                continue
            out[snap.id] = StoredChunk(
                datapoint_id=snap.id,
                text=d.get("text", ""),
                article_id=d.get("article_id", ""),
                title=d.get("title", ""),
                url=d.get("url", ""),
                heading=d.get("heading", ""),
                category_id=d.get("category_id", ""),
            )
        return out
