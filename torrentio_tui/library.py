"""Saved/favorited items, stored as flat JSON (same rationale as history.py)."""

from __future__ import annotations

import contextlib
import json
from dataclasses import asdict

from torrentio_tui.config import library_file
from torrentio_tui.models import MediaKind, SearchResult


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
        try:
            raw = json.loads(self.path.read_text() or "[]")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            with contextlib.suppress(OSError):
                backup = self.path.with_suffix(".json.corrupt")
                backup.write_bytes(self.path.read_bytes())
            return
        if not isinstance(raw, list):
            return
        for row in raw:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            try:
                row["kind"] = MediaKind(row["kind"])
                item = SearchResult(**row)
            except (KeyError, TypeError, ValueError):
                continue
            self._items[self._key(item)] = item

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for item in self._items.values():
            row = asdict(item)
            row["kind"] = item.kind.value
            payload.append(row)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
            raise

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
