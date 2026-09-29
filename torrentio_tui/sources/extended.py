"""Extended source pack: additional torrent indexes, streaming sites,
and Stremio-protocol addons.

All sources here are free, keyless, and use either RSS feeds or public
APIs. They follow the same patterns as the existing sources in
`torrentapi.py`, `anime.py`, and `free.py`.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, open_url
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.sources.stremio import DEFAULT_TRACKERS, StremioSource

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_RES_RE = re.compile(r"\b(2160p|1080p|720p|480p|4k)\b", re.IGNORECASE)


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


def _magnet(info_hash: str, name: str) -> str:
    dn = urllib.parse.quote(name or info_hash)
    parts = [f"magnet:?xt=urn:btih:{info_hash}", f"dn={dn}"]
    parts.extend(f"tr={urllib.parse.quote(t, safe='')}" for t in DEFAULT_TRACKERS)
    return "&".join(parts)


def _fetch_rss(url: str, timeout: float, proxy_url: str | None = None) -> str:
    """Fetch an RSS feed and return the raw XML content."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"}
    try:
        with open_url(url, timeout, proxy_url, headers) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except ProxyError as exc:
        raise SourceError(str(exc)) from exc
    except urllib.error.HTTPError as exc:
        raise SourceError(f"HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SourceError(f"Timeout: {exc}") from exc


def _parse_rss_items(xml_content: str) -> list[dict]:
    """Parse RSS XML and return a list of item dicts."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise SourceError(f"Bad RSS response: {exc}") from exc

    items = []
    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        desc_elem = item.find("description")
        pub_date_elem = item.find("pubDate")

        if title_elem is None or link_elem is None:
            continue

        items.append(
            {
                "title": title_elem.text or "",
                "link": link_elem.text or "",
                "description": desc_elem.text or "" if desc_elem is not None else "",
                "pub_date": pub_date_elem.text or "" if pub_date_elem is not None else "",
            }
        )
    return items


class EZTVRSSSource(Source):
    """EZTV — TV series torrents via RSS feed."""

    id = "eztv-rss"
    name = "EZTV (TV Series Torrents)"
    category = "streams"

    RSS_URL = "https://eztv.re/ezrss/{query}"

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
        url = self.RSS_URL.format(query=urllib.parse.quote(query))

        try:
            content = _fetch_rss(url, self.timeout, self.proxy_url)
        except SourceError:
            return []

        items = _parse_rss_items(content)
        results = []
        for item in items[: self.limit]:
            title = item["title"]
            link = item["link"]
            desc = item["description"]
            pub_date = item["pub_date"]

            magnet_match = re.search(r"magnet:\?[^\"'>\s]+", desc)
            if not magnet_match:
                continue

            stream_url = magnet_match.group(0)
            year = _guess_year(title)
            resolution = _guess_resolution(title)

            seeders_match = re.search(r"Seeders?:\s*(\d+)", desc)
            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]i?B)", desc)

            label_parts = [resolution]
            if seeders_match:
                label_parts.append(f"👤{seeders_match.group(1)}")
            if size_match:
                label_parts.append(f"💾{size_match.group(1)}")
            quality_label = " ".join(label_parts)

            results.append(
                SearchResult(
                    id=f"eztv-rss:{stream_url}",
                    title=title,
                    kind=MediaKind.SERIES,
                    source_id=self.id,
                    year=year,
                    overview=f"{quality_label} · {pub_date}",
                    genres=("tv", "torrent"),
                )
            )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            stream_url = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad EZTV id: {item.id}") from exc
        return [StreamLink(url=stream_url, quality=item.title)]


class TorrentGalaxySource(Source):
    """TorrentGalaxy — torrent index via RSS feed."""

    id = "torrentgalaxy"
    name = "TorrentGalaxy (Torrent Index)"
    category = "streams"

    RSS_URL = "https://torrentgalaxy.to/rss.php?search={query}"

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
        url = self.RSS_URL.format(query=urllib.parse.quote(query))

        try:
            content = _fetch_rss(url, self.timeout, self.proxy_url)
        except SourceError:
            return []

        items = _parse_rss_items(content)
        results = []
        for item in items[: self.limit]:
            title = item["title"]
            link = item["link"]
            desc = item["description"]
            pub_date = item["pub_date"]

            magnet_match = re.search(r"magnet:\?[^\"'>\s]+", desc)
            if not magnet_match:
                continue

            stream_url = magnet_match.group(0)
            year = _guess_year(title)
            resolution = _guess_resolution(title)

            seeders_match = re.search(r"Seeders?:\s*(\d+)", desc)
            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]i?B)", desc)

            label_parts = [resolution]
            if seeders_match:
                label_parts.append(f"👤{seeders_match.group(1)}")
            if size_match:
                label_parts.append(f"💾{size_match.group(1)}")
            quality_label = " ".join(label_parts)

            kind = MediaKind.MOVIE
            if "S0" in title.upper() or "EPISODE" in title.upper():
                kind = MediaKind.SERIES

            results.append(
                SearchResult(
                    id=f"torrentgalaxy:{stream_url}",
                    title=title,
                    kind=kind,
                    source_id=self.id,
                    year=year,
                    overview=f"{quality_label} · {pub_date}",
                    genres=("torrent",),
                )
            )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            stream_url = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad TorrentGalaxy id: {item.id}") from exc
        return [StreamLink(url=stream_url, quality=item.title)]


class MagnetDLSource(Source):
    """MagnetDL — magnet search engine."""

    id = "magnetdl"
    name = "MagnetDL (Magnet Search)"
    category = "streams"

    SEARCH_URL = "https://www.magnetdl.com/search/?q={query}"

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
        url = self.SEARCH_URL.format(query=urllib.parse.quote(query))

        headers = {"User-Agent": _USER_AGENT, "Accept": "text/html"}
        try:
            with open_url(url, self.timeout, self.proxy_url, headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            raise SourceError(f"HTTP {exc.code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        results = []
        # Simple HTML parsing for magnet links
        magnet_pattern = re.compile(r'href="(magnet:\?[^"]+)"[^>]*>([^<]+)</a>')
        for match in magnet_pattern.finditer(content):
            magnet_url = match.group(1)
            title = match.group(2).strip()
            if not title:
                continue

            year = _guess_year(title)
            resolution = _guess_resolution(title)

            results.append(
                SearchResult(
                    id=f"magnetdl:{magnet_url}",
                    title=title,
                    kind=MediaKind.MOVIE,
                    source_id=self.id,
                    year=year,
                    overview=resolution,
                    genres=("magnet",),
                )
            )
            if len(results) >= self.limit:
                break
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            stream_url = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad MagnetDL id: {item.id}") from exc
        return [StreamLink(url=stream_url, quality=item.title)]


class VumooSource(Source):
    """Vumoo — free streaming site (scraping)."""

    id = "vumoo"
    name = "Vumoo (Free Streaming)"
    category = "streams"

    SEARCH_URL = "https://vumoo.to/search/{query}"

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
        url = self.SEARCH_URL.format(query=urllib.parse.quote(query))

        headers = {"User-Agent": _USER_AGENT, "Accept": "text/html"}
        try:
            with open_url(url, self.timeout, self.proxy_url, headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            raise SourceError(f"HTTP {exc.code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        results = []
        # Parse search results from HTML
        result_pattern = re.compile(
            r'<a[^>]*href="(/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>.*?</a>',
            re.DOTALL,
        )
        for match in result_pattern.finditer(content):
            path = match.group(1)
            title = match.group(2).strip()
            if not title:
                continue

            full_url = f"https://vumoo.to{path}"
            year = _guess_year(title)

            results.append(
                SearchResult(
                    id=f"vumoo:{path}",
                    title=title,
                    kind=MediaKind.MOVIE,
                    source_id=self.id,
                    year=year,
                    overview="Free streaming",
                    genres=("streaming",),
                )
            )
            if len(results) >= self.limit:
                break
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            path = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad Vumoo id: {item.id}") from exc
        url = f"https://vumoo.to{path}"
        return [StreamLink(url=url, quality="auto")]


class SolarMovieSource(Source):
    """SolarMovie — free streaming site (scraping)."""

    id = "solarmovie"
    name = "SolarMovie (Free Streaming)"
    category = "streams"

    SEARCH_URL = "https://www.solarmovie.com/search/{query}"

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
        url = self.SEARCH_URL.format(query=urllib.parse.quote(query))

        headers = {"User-Agent": _USER_AGENT, "Accept": "text/html"}
        try:
            with open_url(url, self.timeout, self.proxy_url, headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            raise SourceError(f"HTTP {exc.code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        results = []
        result_pattern = re.compile(
            r'<a[^>]*href="(/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>.*?</a>',
            re.DOTALL,
        )
        for match in result_pattern.finditer(content):
            path = match.group(1)
            title = match.group(2).strip()
            if not title:
                continue

            full_url = f"https://www.solarmovie.com{path}"
            year = _guess_year(title)

            results.append(
                SearchResult(
                    id=f"solarmovie:{path}",
                    title=title,
                    kind=MediaKind.MOVIE,
                    source_id=self.id,
                    year=year,
                    overview="Free streaming",
                    genres=("streaming",),
                )
            )
            if len(results) >= self.limit:
                break
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            path = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad SolarMovie id: {item.id}") from exc
        url = f"https://www.solarmovie.com{path}"
        return [StreamLink(url=url, quality="auto")]


class StremioCommunitySource(StremioSource):
    """Stremio Community addon — free, open source."""

    id = "stremio-community"
    name = "Stremio Community (Free Addon)"
    category = "streams"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://stremio-community.github.io")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Stremio Community")
        super().__init__(**kwargs)


class StremioSuperStreamSource(StremioSource):
    """SuperStream — free Stremio addon with multi-source streams."""

    id = "superstream"
    name = "SuperStream (Free Addon)"
    category = "streams"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://superstream.strem.io")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "SuperStream")
        super().__init__(**kwargs)


class StremioTorrentioCloudSource(StremioSource):
    """Torrentio Cloud — free cloud-based Torrentio instance."""

    id = "torrentio-cloud"
    name = "Torrentio Cloud (Free)"
    category = "streams"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://torrentio-cloud.strem.fun")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Torrentio Cloud")
        super().__init__(**kwargs)
