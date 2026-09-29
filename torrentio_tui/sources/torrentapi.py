"""Torrent-index sources with real, keyless JSON APIs.

YTS exposes its official API (movies only) — search returns genuine
playable magnets, resolved through the app's usual webtorrent/peerflix
bridge or a debrid-backed addon. Honors `network.proxy_url` via
`torrentio_tui.proxy.open_url`.

RARBG uses torrentapi.org/pubapi_v2.php — returns magnets that need
the torrent bridge (webtorrent/peerflix or debrid).
"""

from __future__ import annotations

import contextlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, open_url
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.sources.stremio import DEFAULT_TRACKERS

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
    with contextlib.suppress(ValueError):
        return int(m.group(1))
    return None


def _magnet(info_hash: str, name: str) -> str:
    dn = urllib.parse.quote(name or info_hash)
    parts = [f"magnet:?xt=urn:btih:{info_hash}", f"dn={dn}"]
    parts.extend(f"tr={urllib.parse.quote(t, safe='')}" for t in DEFAULT_TRACKERS)
    return "&".join(parts)


def _read_json(url: str, timeout: float, proxy_url: str | None) -> dict | list:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    last_exc: Exception | None = None
    for attempt in range(2):  # one retry on transient 5xx
        try:
            with open_url(url, timeout, proxy_url, headers) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code not in (500, 502, 503, 504) or attempt == 1:
                raise SourceError(f"Request failed (HTTP {exc.code}): {url}") from exc
            last_exc = exc
            time.sleep(1.0)
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error for {url}: {exc.reason}") from exc
        except (json.JSONDecodeError, TimeoutError) as exc:
            raise SourceError(f"Bad response from {url}: {exc}") from exc
    raise SourceError(f"Request failed after retry: {url}") from last_exc


class YTSSource(Source):
    """YTS/YIFY movies via the official API — high-quality movie torrents
    as real magnets (movies only; series/anime return no results)."""

    id = "yts"
    name = "YTS / YIFY Movies"
    category = "streams"

    # Per the API's own notice, the base moved off yts.mx mirrors.
    API = "https://movies-api.accel.li/api/v2"

    def __init__(
        self,
        api_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.api_url = (api_url or self.API).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        url = (
            f"{self.api_url}/list_movies.json?query_term={urllib.parse.quote(query)}"
            f"&limit={self.limit}&sort_by=like_count&order_by=desc"
        )
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict) or data.get("status") != "ok":
            raise SourceError("YTS API returned an error")
        results = []
        for movie in (data.get("data") or {}).get("movies") or []:
            if not isinstance(movie, dict):
                continue
            movie_id = movie.get("id")
            if movie_id is None:
                continue
            results.append(
                SearchResult(
                    id=f"yts:{movie_id}",
                    title=str(movie.get("title", f"YTS {movie_id}")),
                    kind=MediaKind.MOVIE,
                    source_id=self.id,
                    year=movie.get("year") if isinstance(movie.get("year"), int) else None,
                    poster_url=movie.get("medium_cover_image"),
                    overview=movie.get("summary"),
                    genres=tuple(str(g) for g in movie.get("genres") or []),
                )
            )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            movie_id = int(item.id.split(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SourceError(f"Bad YTS id: {item.id}") from exc
        url = f"{self.api_url}/movie_details.json?movie_id={movie_id}&with_cast=false"
        data = _read_json(url, self.timeout, self.proxy_url)
        movie = (data.get("data") or {}).get("movie") if isinstance(data, dict) else None
        if not isinstance(movie, dict):
            raise SourceError("YTS has no details for this title")
        links = []
        for torrent in movie.get("torrents") or []:
            if not isinstance(torrent, dict) or not torrent.get("hash"):
                continue
            quality = str(torrent.get("quality", "auto"))
            seeds = torrent.get("seeds", 0)
            size = torrent.get("size", "")
            label = quality
            if seeds:
                label += f" 👤{seeds}"
            if size:
                label += f" 💾{size}"
            links.append(
                StreamLink(
                    url=_magnet(str(torrent["hash"]), f"{item.title} {quality}"),
                    quality=label,
                )
            )
        return links


class RARBGSource(Source):
    """RARBG via torrentapi.org — movies & series as magnets."""

    id = "rarbg"
    name = "RARBG (torrentapi.org)"
    category = "streams"

    API = "https://torrentapi.org/pubapi_v2.php"
    APP_ID = "torrentio-tui"

    def __init__(
        self,
        api_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.api_url = (api_url or self.API).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        url = f"{self.api_url}?get_token=get_token&app_id={urllib.parse.quote(self.APP_ID)}"
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict) or "token" not in data:
            raise SourceError("RARBG: failed to get token")
        self._token = str(data["token"])
        return self._token

    def _search_api(self, query: str, mode: str = "search") -> list[dict]:
        token = self._get_token()
        encoded_query = urllib.parse.quote(query.strip())
        url = (
            f"{self.api_url}?mode={mode}&search_string={encoded_query}"
            f"&format=json_extended&token={urllib.parse.quote(token)}"
            f"&app_id={urllib.parse.quote(self.APP_ID)}&limit={self.limit}"
        )
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict):
            raise SourceError("RARBG: unexpected response format")
        if data.get("error_code") == 20:
            # token expired
            self._token = None
            return self._search_api(query, mode)
        if "error" in data:
            raise SourceError(f"RARBG API error: {data['error']}")
        return data.get("torrent_results") or []

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results = []
        for item in self._search_api(query):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            if not title:
                continue
            info_hash = item.get("info_hash")
            if not info_hash:
                # torrentapi.org's `download` field is already a full
                # magnet: URL — extract the btih hash so get_streams
                # doesn't double-wrap it into magnet:?xt=urn:btih:magnet:?...
                download = str(item.get("download") or "")
                m = re.search(r"btih:([A-Za-z0-9]{32,40})", download, re.IGNORECASE)
                info_hash = m.group(1) if m else None
            if not info_hash:
                continue
            year = _guess_year(title)
            resolution = _guess_resolution(title)
            seeders = item.get("seeders", 0)
            size = item.get("size", "")
            label_parts = [resolution]
            if seeders:
                label_parts.append(f"👤{seeders}")
            if size:
                label_parts.append(f"💾{size}")
            quality_label = " ".join(label_parts)
            kind = MediaKind.MOVIE
            if "S0" in title.upper() or "EPISODE" in title.upper():
                kind = MediaKind.SERIES
            results.append(
                SearchResult(
                    id=f"rarbg:{info_hash}",
                    title=title,
                    kind=kind,
                    source_id=self.id,
                    year=year,
                    overview=quality_label,
                    genres=(),
                )
            )
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            info_hash = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad RARBG id: {item.id}") from exc
        magnet = _magnet(info_hash, item.title)
        return [StreamLink(url=magnet, quality=item.title)]


class Thirteen37xSource(Source):
    """1337x — torrent index via RSS feed."""

    id = "1337x"
    name = "1337x (Torrent Index)"
    category = "streams"

    RSS_URL = "https://1337x.to/rss/search/{query}/1/"

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
            import xml.etree.ElementTree as ET

            headers = {"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise SourceError(f"1337x search failed: {exc}") from exc

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item")[: self.limit]:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            desc = desc_elem.text or ""
            pub_date = pub_date_elem.text or ""

            # Extract magnet or torrent link from description
            magnet_match = re.search(r"magnet:\?[^\"'>\s]+", desc)
            torrent_match = re.search(r"https?://[^\"'>\s]+\.torrent", desc)

            if magnet_match:
                stream_url = magnet_match.group(0)
            elif torrent_match:
                stream_url = torrent_match.group(0)
            else:
                stream_url = link

            year = _guess_year(title)
            resolution = _guess_resolution(title)
            seeders_match = re.search(r"Seeders?:\s*(\d+)", desc)
            leechers_match = re.search(r"Leechers?:\s*(\d+)", desc)
            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]i?B)", desc)

            label_parts = [resolution]
            if seeders_match:
                label_parts.append(f"👤{seeders_match.group(1)}")
            if leechers_match:
                label_parts.append(f"📥{leechers_match.group(1)}")
            if size_match:
                label_parts.append(f"💾{size_match.group(1)}")
            quality_label = " ".join(label_parts)

            kind = MediaKind.MOVIE
            if "S0" in title.upper() or "EPISODE" in title.upper():
                kind = MediaKind.SERIES

            results.append(
                SearchResult(
                    id=f"1337x:{stream_url}",
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
            raise SourceError(f"Bad 1337x id: {item.id}") from exc
        return [StreamLink(url=stream_url, quality=item.title)]


class PirateBaySource(Source):
    """The Pirate Bay — torrent index via RSS."""

    id = "piratebay"
    name = "The Pirate Bay"
    category = "streams"

    RSS_URL = "https://thepiratebay.org/rss.php?q={query}"

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
            import xml.etree.ElementTree as ET

            headers = {"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise SourceError(f"Pirate Bay search failed: {exc}") from exc

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item")[: self.limit]:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            desc = desc_elem.text or ""
            pub_date = pub_date_elem.text or ""

            # TPB uses magnet links in description
            magnet_match = re.search(r"magnet:\?[^\"'>\s]+", desc)

            if not magnet_match:
                continue

            stream_url = magnet_match.group(0)
            year = _guess_year(title)
            resolution = _guess_resolution(title)

            seeders_match = re.search(r"Seeders?:\s*(\d+)", desc)
            size_match = re.search(r"Size\s+([\d.]+\s*[GM]i?B)", desc)

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
                    id=f"piratebay:{stream_url}",
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
            raise SourceError(f"Bad Pirate Bay id: {item.id}") from exc
        return [StreamLink(url=stream_url, quality=item.title)]
