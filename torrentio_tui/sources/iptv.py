"""IPTV/Live TV source: parses M3U playlists for live channels.

Add an M3U playlist URL or local file path to watch live TV channels.
Supports standard M3U format with EXTINF tags for channel info.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.3 (+https://github.com/yubiiixtreme/torrentio-tui)"

# Regex to parse M3U EXTINF lines
EXTINF_RE = re.compile(r"#EXTINF:-?\d+(?:\s+([^=]+)=\"([^\"]*)\")*\s*,(.+)$")

# Common attribute patterns
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


class IPTVSource(Source):
    """Load live TV channels from an M3U playlist (URL or local file)."""

    id = "iptv"
    name = "IPTV (M3U Playlist)"
    category = "live"
    supports_live = True

    def __init__(
        self,
        m3u_url: str | None = None,
        m3u_path: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
    ) -> None:
        self.m3u_url = m3u_url
        self.m3u_path = Path(m3u_path).expanduser() if m3u_path else None
        self.timeout = timeout
        self.proxy_url = proxy_url
        self._channels: list[dict] = []
        self._loaded = False

    def _load_playlist(self) -> None:
        """Load and parse the M3U playlist."""
        from torrentio_tui.proxy import open_url

        if self._loaded:
            return

        content = ""
        if self.m3u_url:
            try:
                with open_url(
                    self.m3u_url,
                    self.timeout,
                    self.proxy_url,
                    {"User-Agent": _USER_AGENT, "Accept": "*/*"},
                ) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                raise SourceError(f"Failed to fetch M3U: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise SourceError(f"Network error fetching M3U: {exc.reason}") from exc
            except TimeoutError as exc:
                raise SourceError(f"Timeout fetching M3U: {exc}") from exc
            except OSError as exc:
                raise SourceError(f"Network error fetching M3U: {exc}") from exc
        elif self.m3u_path and self.m3u_path.exists():
            try:
                content = self.m3u_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise SourceError(f"Failed to read M3U file: {exc}") from exc
        else:
            raise SourceError("No M3U URL or path configured")

        self._channels = self._parse_m3u(content)
        self._loaded = True

    def _parse_m3u(self, content: str) -> list[dict]:
        """Parse M3U content into channel list."""
        channels = []
        lines = content.splitlines()
        current_extinf: dict | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                # Parse EXTINF line
                match = EXTINF_RE.match(line)
                if match:
                    # Extract attributes
                    attrs = {}
                    extinf_part = line[8:]  # Remove "#EXTINF:"
                    comma_idx = extinf_part.rfind(",")
                    if comma_idx >= 0:
                        attr_part = extinf_part[:comma_idx]
                        name = extinf_part[comma_idx + 1 :].strip()
                        for attr_match in ATTR_RE.finditer(attr_part):
                            attrs[attr_match.group(1).lower()] = attr_match.group(2)
                        attrs["name"] = name
                        current_extinf = attrs
                    else:
                        # No comma, just duration
                        current_extinf = {"name": "Unknown"}
                else:
                    current_extinf = {"name": "Unknown"}
            elif line.startswith("#"):
                # Other tags (EXTGRP, EXTLOGO, etc.)
                if current_extinf:
                    if line.startswith("#EXTGRP:"):
                        current_extinf["group"] = line[8:].strip()
                    elif line.startswith("#EXTLOGO:"):
                        current_extinf["logo"] = line[9:].strip()
            else:
                # This should be the stream URL
                if current_extinf:
                    current_extinf["url"] = line
                    channels.append(current_extinf)
                    current_extinf = None
                elif line and not line.startswith("#"):
                    # URL without EXTINF
                    channels.append({"name": f"Channel {len(channels) + 1}", "url": line})

        return channels

    def search(self, query: str) -> list[SearchResult]:
        """Search channels by name or group."""
        self._load_playlist()
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        results = []
        for ch in self._channels:
            name = ch.get("name", "").lower()
            group = ch.get("group", "").lower()
            if query_lower in name or query_lower in group:
                results.append(
                    SearchResult(
                        id=ch.get("url", ""),
                        title=ch.get("name", "Unknown Channel"),
                        kind=MediaKind.LIVE,
                        source_id=self.id,
                        year=None,
                        poster_url=ch.get("logo"),
                        overview=f"Group: {ch.get('group', 'Unknown')}",
                        genres=(ch.get("group", "General"),),
                    )
                )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        """Live channels have a single 'episode' (the stream itself)."""
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """Return the stream URL for the channel."""
        self._load_playlist()
        # Find the channel by URL (id)
        for ch in self._channels:
            if ch.get("url") == item.id:
                return [
                    StreamLink(
                        url=ch["url"],
                        quality="live",
                        is_live=True,
                    )
                ]
        # Fallback: return the item.id as stream URL
        return [StreamLink(url=item.id, quality="live", is_live=True)]

    def close(self) -> None:
        pass


class IPTVOrgSource(IPTVSource):
    """Free world live TV via the iptv-org project playlist.

    100% free, no key, no account — thousands of public channels.
    Ships with the world index playlist as the default; point
    ``m3u_url`` at a country/category playlist from
    https://iptv-org.github.io/iptv/ to narrow it down.
    """

    id = "iptv-org"
    name = "IPTV-org (Free World TV)"

    WORLD_PLAYLIST = "https://iptv-org.github.io/iptv/index.m3u"

    def __init__(
        self,
        m3u_url: str | None = None,
        m3u_path: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            m3u_url=m3u_url or self.WORLD_PLAYLIST,
            m3u_path=m3u_path,
            timeout=timeout,
        )
