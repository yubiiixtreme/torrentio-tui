"""Core data types shared across sources, player backends, and the UI.

Every `Source` implementation speaks these types so the rest of the app
never needs to know which site or scraper produced them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MediaKind(Enum):
    MOVIE = "movie"
    SERIES = "series"
    ANIME = "anime"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One row returned by `Source.search()`."""

    id: str
    """Opaque id the owning source can later resolve (path, slug, API id, ...)."""
    title: str
    kind: MediaKind
    source_id: str
    """id of the `Source` that produced this result, for routing follow-up calls."""
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None


@dataclass(frozen=True, slots=True)
class Episode:
    id: str
    title: str
    season: int | None = None
    number: int | None = None


@dataclass(frozen=True, slots=True)
class StreamLink:
    """A single playable link at a given quality."""

    url: str
    quality: str
    """e.g. "1080p", "720p", "auto"."""
    headers: dict[str, str] = field(default_factory=dict)
    """Extra HTTP headers (referer/user-agent/cookies) some sources require for playback."""
    subtitle_url: str | None = None
    is_live: bool = False


@dataclass(slots=True)
class HistoryEntry:
    item_id: str
    source_id: str
    title: str
    episode_label: str | None
    position_seconds: float
    duration_seconds: float | None
    watched_at: float
