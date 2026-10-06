"""More free torrent indexes via RSS feeds (no API keys, no accounts).

Every class here shares one RSS search pattern: fetch the index's RSS
search feed, pull magnet links out of the item descriptions, and return
them as `SearchResult`s. Magnets play through the app's usual
webtorrent/peerflix bridge or a debrid-backed addon.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, open_url
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.5 (+https://github.com/yubiiixtreme/torrentio-tui)"

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_RES_RE = re.compile(r"\b(2160p|1080p|720p|480p|4k)\b", re.IGNORECASE)
_MAGNET_RE = re.compile(r"magnet:\?[^\"'>\s]+")


def _guess_resolution(text: str) -> str:
    m = _RES_RE.search(text or "")
    if not m:
        return "auto"
    token = m.group(1).lower()
    return "2160p" if token == "4k" else token


def _guess_year(text: str) -> int | None:
    m = _YEAR_RE.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _guess_kind(title: str, default: MediaKind = MediaKind.MOVIE) -> MediaKind:
    upper = (title or "").upper()
    if re.search(r"\bS\d{1,2}E\d{1,2}\b", upper) or "SEASON" in upper or "EPISODE" in upper:
        return MediaKind.SERIES
    return default


class BaseRSSIndexSource(Source):
    """Shared RSS-search machinery for torrent indexes."""

    category = "streams"
    rss_url: str = ""
    limit: int = 20

    def __init__(
        self,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        url = self.rss_url.format(query=urllib.parse.quote(query))
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"}
        try:
            with open_url(url, self.timeout, self.proxy_url, headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceError(f"HTTP {code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results: list[SearchResult] = []
        for item in root.findall(".//item")[: self.limit]:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")
            if title_elem is None or link_elem is None:
                continue
            title = title_elem.text or ""
            desc = desc_elem.text or "" if desc_elem is not None else ""
            pub_date = pub_date_elem.text or "" if pub_date_elem is not None else ""
            magnet_match = _MAGNET_RE.search(desc)
            if not magnet_match:
                continue
            magnet = magnet_match.group(0)
            year = _guess_year(title)
            resolution = _guess_resolution(title)
            seeders = re.search(r"Seeders?:\s*(\d+)", desc)
            size = re.search(r"Size:\s*([\d.]+\s*[GM]i?B)", desc)
            parts = [resolution]
            if seeders:
                parts.append(f"👤{seeders.group(1)}")
            if size:
                parts.append(f"💾{size.group(1)}")
            results.append(
                SearchResult(
                    id=f"{self.id}:{magnet}",
                    title=title,
                    kind=_guess_kind(title),
                    source_id=self.id,
                    year=year,
                    overview=f"{' '.join(parts)} · {pub_date}".strip(" ·"),
                    genres=("torrent",),
                )
            )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            magnet = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad {self.id} id: {item.id}") from exc
        return [StreamLink(url=magnet, quality=item.title)]


class LimeTorrentsSource(BaseRSSIndexSource):
    """LimeTorrents — general torrent index via RSS."""

    id = "limetorrents"
    name = "LimeTorrents (Torrent Index)"
    rss_url = "https://www.limetorrents.info/rss/search/{query}/"


class TorrentDownloadsSource(BaseRSSIndexSource):
    """TorrentDownloads — general torrent index via RSS."""

    id = "torrentdownloads"
    name = "TorrentDownloads (Torrent Index)"
    rss_url = "https://www.torrentdownloads.pro/rss/search/{query}"


class GloDLSSource(BaseRSSIndexSource):
    """GloDLS — general torrent index via RSS."""

    id = "glodls"
    name = "GloDLS (Torrent Index)"
    rss_url = "https://glodls.to/rss/search/{query}"
