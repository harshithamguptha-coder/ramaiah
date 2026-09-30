"""In-process cache of parsed dataset frames.

``dataset_service`` parses an upload once; ``classical_service`` then needs the
*same* DataFrame to train on. Rather than re-reading and re-parsing the file
(which for a 20k-row XLSX is the most expensive thing in the request), the
parsed frame is parked here keyed by ``file_id`` and picked up downstream.

This follows the same seam style as ``utils/store.py``: it is a single, boring
module that owns one concern, so swapping it for a disk-backed or shared cache
never touches a service. It is deliberately in-process and best-effort - a miss
returns ``None`` and the caller falls back to re-reading the file.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


class DatasetFrameCache:
    """Bounded, thread-safe LRU cache of parsed DataFrames."""

    def __init__(self, max_items: int = 8) -> None:
        self._max_items = max(1, max_items)
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()

    def put(self, key: str, frame: Any) -> None:
        """Store a frame under ``key``, evicting the least-recently-used entry."""
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
            self._items[key] = frame
            while len(self._items) > self._max_items:
                evicted, _ = self._items.popitem(last=False)
                logger.debug("Evicted cached frame %s", evicted)

    def get(self, key: str) -> Any | None:
        """Return a cached frame, or ``None`` on a miss."""
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def drop(self, key: str) -> None:
        """Remove one entry (used when an analysis is deleted)."""
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        """Drop every cached frame."""
        with self._lock:
            self._items.clear()


_cache = DatasetFrameCache(max_items=max(2, settings.store_max_items // 4))


def get_cache() -> DatasetFrameCache:
    """Return the process-wide frame cache singleton."""
    return _cache


def put_frame(file_id: str | None, frame: Any) -> None:
    """Cache ``frame`` for ``file_id`` (no-op when there is no id)."""
    if file_id:
        _cache.put(file_id, frame)


def get_frame(file_id: str | None) -> Any | None:
    """Return a cached frame for ``file_id``, or ``None``."""
    if not file_id:
        return None
    return _cache.get(file_id)


def drop_frame(file_id: str | None) -> None:
    """Evict the frame for ``file_id``, if any."""
    if file_id:
        _cache.drop(file_id)
