"""'Continue watching' tracking, stored as flat JSON.

Deliberately not a database — this is meant to be easy to inspect/edit by
hand, matching the "no telemetry, everything local" spirit of both
reference projects.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict

from torrentio_tui.config import history_file
from torrentio_tui.models import HistoryEntry


class HistoryStore:
    def __init__(self) -> None:
        self.path = history_file()
        self._entries: dict[str, HistoryEntry] = {}
        self._load()

    def _key(self, source_id: str, item_id: str) -> str:
        return f"{source_id}:{item_id}"

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        for row in raw:
            entry = HistoryEntry(**row)
            self._entries[self._key(entry.source_id, entry.item_id)] = entry

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self._entries.values()]
        self.path.write_text(json.dumps(payload, indent=2))

    def record(
        self,
        *,
        item_id: str,
        source_id: str,
        title: str,
        episode_label: str | None,
        position_seconds: float,
        duration_seconds: float | None,
    ) -> None:
        entry = HistoryEntry(
            item_id=item_id,
            source_id=source_id,
            title=title,
            episode_label=episode_label,
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
            watched_at=time.time(),
        )
        self._entries[self._key(source_id, item_id)] = entry
        self._save()

    def get(self, source_id: str, item_id: str) -> HistoryEntry | None:
        return self._entries.get(self._key(source_id, item_id))

    def recent(self, limit: int = 20) -> list[HistoryEntry]:
        return sorted(self._entries.values(), key=lambda e: e.watched_at, reverse=True)[:limit]
