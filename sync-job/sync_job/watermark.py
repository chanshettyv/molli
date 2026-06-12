"""Firestore-backed sync watermark.

Stores the timestamp of the last successful sync so incremental runs only
process articles modified since then. Also stores the set of article IDs that
failed to fetch on the previous run, so they are retried on the next run even
though the watermark has advanced past them (otherwise a transient fetch error
would silently drop an article from the index until it is next edited).

Document path: collection ``sync_state``, document ``document360``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.cloud import firestore

_COLLECTION = "sync_state"
_DOCUMENT = "document360"
_FIELD = "last_synced_at"
_FAILED_FIELD = "failed_article_ids"


class WatermarkStore:
    """Read/write the incremental-sync watermark + failed-IDs in Firestore."""

    def __init__(self, project_id: str, database: str = "(default)") -> None:
        self._client = firestore.Client(project=project_id, database=database)
        self._ref = self._client.collection(_COLLECTION).document(_DOCUMENT)

    def read(self) -> datetime | None:
        """Return the last successful sync time, or None for a first run."""
        snapshot = self._ref.get()
        if not snapshot.exists:
            return None
        value = snapshot.to_dict().get(_FIELD)
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).astimezone(UTC)
        except (ValueError, TypeError):
            return None

    def write(self, when: datetime) -> None:
        """Persist a new watermark. Pass the time the sync STARTED, not ended,
        to avoid missing articles modified mid-run."""
        when_utc = when.astimezone(UTC) if when.tzinfo else when.replace(tzinfo=UTC)
        self._ref.set({_FIELD: when_utc.isoformat()}, merge=True)

    def read_failed(self) -> list[str]:
        """Return article IDs that failed to fetch on a previous run and should
        be retried this run regardless of the watermark. Empty list if none."""
        snapshot = self._ref.get()
        if not snapshot.exists:
            return []
        value = snapshot.to_dict().get(_FAILED_FIELD)
        return list(value) if isinstance(value, list) else []

    def write_failed(self, article_ids: list[str]) -> None:
        """Persist the set of article IDs that failed this run, so the next run
        retries them even though the watermark has advanced past them. Pass an
        empty list to clear (all previously-failed articles succeeded)."""
        self._ref.set({_FAILED_FIELD: list(article_ids)}, merge=True)
