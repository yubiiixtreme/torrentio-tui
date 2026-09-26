"""Saved/favorited items, stored as flat JSON (same rationale as history.py)."""
from __future__ import annotations

import json
from dataclasses import asdict

from stream_tui.config import library_file
from stream_tui.models import MediaKind, SearchResult


class LibraryStore:
    def __init__(self) -> None:
        self.path = library_file()
        self._items: dict[str, SearchResult] = {}
        self._load()

    def _key(self, item: SearchResult) -> str:
        return f"{item.source_id}:{item.id}"

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        for row in raw:
            row = dict(row)
            row["kind"] = MediaKind(row["kind"])
            item = SearchResult(**row)
            self._items[self._key(item)] = item

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for item in self._items.values():
            row = asdict(item)
            row["kind"] = item.kind.value
            payload.append(row)
        self.path.write_text(json.dumps(payload, indent=2))

    def add(self, item: SearchResult) -> None:
        self._items[self._key(item)] = item
        self._save()

    def remove(self, item: SearchResult) -> None:
        self._items.pop(self._key(item), None)
        self._save()

    def contains(self, item: SearchResult) -> bool:
        return self._key(item) in self._items

    def all(self) -> list[SearchResult]:
        return list(self._items.values())
