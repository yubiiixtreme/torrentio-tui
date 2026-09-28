"""'Continue watching' tracking, stored as flat JSON.

Deliberately not a database — this is meant to be easy to inspect/edit by
hand, matching the "no telemetry, everything local" spirit of both
reference projects.
"""

from __future__ import annotations

import contextlib
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
        try:
            raw = json.loads(self.path.read_text() or "[]")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # A corrupt/interrupted write must never kill startup — back it
            # up and start empty so the user can inspect/recover it.
            with contextlib.suppress(OSError):
                backup = self.path.with_suffix(".json.corrupt")
                backup.write_bytes(self.path.read_bytes())
            return
        if not isinstance(raw, list):
            return
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                entry = HistoryEntry(**row)
            except TypeError:
                continue
            self._entries[self._key(entry.source_id, entry.item_id)] = entry

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self._entries.values()]
        # Atomic write: a crash mid-write must not leave a half-written
        # JSON file that then fails to parse on next startup.
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
            raise

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
