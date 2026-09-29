"""Pluggable persistence layer.

The prototype keeps analyses in process memory. The ``AnalysisRepository``
protocol below is the single seam where a real database (Postgres, Mongo,
SQLModel, ...) will be dropped in later — nothing above this module knows or
cares how an analysis is stored.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol, runtime_checkable

from utils.ids import utc_now_iso


@runtime_checkable
class AnalysisRepository(Protocol):
    """Storage contract every repository implementation must satisfy."""

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace an analysis record and return the stored version."""
        ...

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        """Return a single analysis record, or ``None`` when unknown."""
        ...

    def list(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent analyses, newest first."""
        ...

    def delete(self, analysis_id: str) -> bool:
        """Remove an analysis. Returns ``True`` when something was removed."""
        ...


class InMemoryAnalysisRepository:
    """Thread-safe, bounded, in-process implementation of the repository.

    Suitable for the prototype and local development only: state is lost on
    restart and is not shared between workers.
    """

    def __init__(self, max_items: int = 50) -> None:
        self._max_items = max_items
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stored = dict(record)
            stored.setdefault("created_at", utc_now_iso())
            stored["updated_at"] = utc_now_iso()
            self._items[stored["analysis_id"]] = stored

            if len(self._items) > self._max_items:
                oldest = sorted(self._items.values(), key=lambda r: r.get("created_at", ""))
                for record_to_drop in oldest[: len(self._items) - self._max_items]:
                    self._items.pop(record_to_drop["analysis_id"], None)

            return stored

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._items.get(analysis_id)
            return dict(record) if record else None

    def list(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            ordered = sorted(
                self._items.values(), key=lambda r: r.get("created_at", ""), reverse=True
            )
            return [dict(r) for r in ordered[:limit]]

    def delete(self, analysis_id: str) -> bool:
        with self._lock:
            return self._items.pop(analysis_id, None) is not None


_repository: AnalysisRepository | None = None


def get_repository() -> AnalysisRepository:
    """Return the process-wide repository singleton."""
    global _repository
    if _repository is None:
        from config import settings

        _repository = InMemoryAnalysisRepository(max_items=settings.store_max_items)
    return _repository
