"""Document360 API client.

Phase 1: implement list_articles, get_article, and modified-since filtering.
API docs: https://apidocs.document360.com/
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class Document360Client:
    def __init__(self, api_key: str, base_url: str = "https://apihub.document360.io/v2") -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"api_token": api_key},
            timeout=30.0,
        )

    async def list_articles(self, modified_since: datetime | None = None) -> list[dict[str, Any]]:
        """List articles, optionally filtered to those modified since a given time."""
        raise NotImplementedError("Phase 1")

    async def get_article(self, article_id: str) -> dict[str, Any]:
        """Fetch a single article's full content."""
        raise NotImplementedError("Phase 1")

    async def aclose(self) -> None:
        await self._client.aclose()
