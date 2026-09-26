"""A real, working `Source` that indexes local video files.

Exists so the app is fully runnable end-to-end (search -> pick -> play)
without needing any external/legally-sensitive scraper wired up yet. Point
it at a folder of your own media via `TORRENTIO_TUI_LOCAL_DIR` or the
`~/Videos` default.
"""

from __future__ import annotations

import os
from pathlib import Path

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


class LocalSource(Source):
    id = "local"
    name = "Local Files"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(os.environ.get("TORRENTIO_TUI_LOCAL_DIR", "~/Videos")).expanduser()

    def _iter_files(self):
        if not self.root.exists():
            return
        yield from (p for p in self.root.rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS)

    def search(self, query: str) -> list[SearchResult]:
        query_lower = query.lower().strip()
        results = []
        for path in self._iter_files():
            if not query_lower or query_lower in path.stem.lower():
                results.append(
                    SearchResult(
                        id=str(path),
                        title=path.stem,
                        kind=MediaKind.MOVIE,
                        source_id=self.id,
                    )
                )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        return [StreamLink(url=item.id, quality="local")]
