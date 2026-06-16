"""Shared retrieval primitives: query embedding + Vector Search access.

Used by sync-job (indexing) and chat-service (RAG answers). Single source of
truth so the two services can't drift on embedding task types or index config.
"""

from molli_shared.retrieval.embedding import Embedder
from molli_shared.retrieval.index_store import IndexedChunk, VectorIndex

__all__ = ["Embedder", "VectorIndex", "IndexedChunk"]