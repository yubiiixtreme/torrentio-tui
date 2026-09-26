"""The plugin contract every content source implements.

This is the ONLY interface the rest of the app talks to. Add a new source by:

  1. Subclassing `Source` below.
  2. Registering an instance in `stream_tui/sources/registry.py`.
  3. Adding its `id` to `sources.enabled` in the config file.

Nothing about scraping, auth, DRM, or which sites are legal to pull from is
decided here on purpose — that's the part left to you. See `example.py` for
an annotated stub, and `local.py` for a real, working reference
implementation (it just indexes a folder on disk).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from stream_tui.models import Episode, SearchResult, StreamLink


class SourceError(Exception):
    """Raise this (instead of letting raw exceptions escape) for anything
    the UI should show as a friendly error: network failures, site changes,
    auth walls, etc."""


class Source(ABC):
    id: str
    """Stable short id, e.g. "local", "myscraper". Used in config + routing."""
    name: str
    """Human-readable name shown in the UI."""
    supports_live: bool = False

    @abstractmethod
    def search(self, query: str) -> list[SearchResult]:
        """Return matches for a free-text query. Should not raise on "no
        results" — return an empty list. Raise `SourceError` on failure."""

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        """Return episodes for a series. Movies/live items can ignore this;
        default implementation returns a single synthetic episode so callers
        can treat everything uniformly."""
        return [Episode(id=item.id, title=item.title)]

    @abstractmethod
    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """Resolve one or more playable `StreamLink`s (ideally multiple
        qualities) for the given item/episode."""

    def close(self) -> None:
        """Override to release sessions/connections. No-op by default."""
        return None
