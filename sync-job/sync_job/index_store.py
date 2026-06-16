"""Moved to molli_shared.retrieval.index_store. Re-export for compatibility."""
from molli_shared.retrieval.index_store import IndexedChunk, VectorIndex

__all__ = ["IndexedChunk", "VectorIndex"]