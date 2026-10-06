"""Extended torrent sources for movies and series.

Adds support for:
- 1337x (movies, series, anime, games via RSS/HTML)
- The Pirate Bay (via RSS/HTML)
- RARBG mirrors (additional torrentapi.org endpoints)
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
    for attempt in range(2):
        try:
            with open_url(url, timeout, proxy_url, headers) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code not in (500, 502, 503, 504) or attempt == 1:
                raise SourceError(f"Request failed (HTTP {code}): {url}") from exc
            last_exc = exc
            time.sleep(1.0)
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error for {url}: {exc.reason}") from exc
        except (json.JSONDecodeError, TimeoutError) as exc:
            raise SourceError(f"Bad response from {url}: {exc}") from exc
    raise SourceError(f"Request failed after retry: {url}") from last_exc


def _fetch_html(url: str, timeout: float, proxy_url: str | None) -> str:
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html"}
    try:
        with open_url(url, timeout, proxy_url, headers) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except ProxyError as exc:
        raise SourceError(str(exc)) from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SourceError(f"Timeout: {exc}") from exc


class BaseHTMLSource(Source):
    """Base class for HTML-scraping torrent sources."""

    category = "streams"
    supports_live = False

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def _extract_torrents(self, html: str) -> list[dict]:
        """Extract torrent info from HTML. Override in subclasses."""
        raise NotImplementedError


class Thirteen37xSource(Source):
    """1337x - movies, series, anime, games via RSS feeds."""

    id = "1337x"
    name = "1337x (Movies, Series, Anime)"
    category = "streams"

    BASE_URL = "https://1337x.to"
    SEARCH_URL = "https://1337x.to/search/{query}/1/"
    RSS_URL = "https://1337x.to/rss/search/{query}/"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        # Use RSS feed for search
        url = self.RSS_URL.format(query=urllib.parse.quote(query))

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"},
            )
            with open_url(url, self.timeout, self.proxy_url, req.headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise SourceError(f"1337x search failed: {exc}") from exc

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            desc = (desc_elem.text or "") if desc_elem is not None else ""
            pub_date = (pub_date_elem.text or "") if pub_date_elem is not None else ""

            # Extract info hash from link (format: /torrent/123456/name/)
            hash_match = re.search(r"/torrent/([a-f0-9]{40})/", link)
            info_hash = hash_match.group(1) if hash_match else ""

            # Parse description for size, seeds, peers
            size = ""
            seeds = ""
            peers = ""
            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]iB)", desc, re.IGNORECASE)
            if size_match:
                size = f" {size_match.group(1)}"
            seed_match = re.search(r"Seeders:\s*(\d+)", desc, re.IGNORECASE)
            if seed_match:
                seeds = f" 👤{seed_match.group(1)}"
            peer_match = re.search(r"Leechers:\s*(\d+)", desc, re.IGNORECASE)
            if peer_match:
                peers = f" 📥{peer_match.group(1)}"

            quality = _guess_resolution(title)
            year = _guess_year(title)

            # Determine kind from title/category
            kind = MediaKind.MOVIE
            if re.search(r"S\d+E\d+", title, re.IGNORECASE) or "episode" in title.lower():
                kind = MediaKind.SERIES
            elif any(x in title.lower() for x in ("anime", "hentai")):
                kind = MediaKind.ANIME

            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            results.append(
                SearchResult(
                    id=f"1337x:{info_hash}:{link}",
                    title=clean_title,
                    kind=kind,
                    source_id=self.id,
                    year=year,
                    poster_url=None,
                    overview=f"{quality} · {pub_date}{size}{seeds}{peers}",
                    genres=("torrent",),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        parts = item.id.split(":", 2)
        if len(parts) < 2:
            return []
        _, info_hash = parts[0], parts[1]
        if not info_hash:
            # Try to fetch from the page
            url = parts[2] if len(parts) > 2 else ""
            if url:
                html = _fetch_html(url, self.timeout, self.proxy_url)
                hash_match = re.search(r"([a-f0-9]{40})", html)
                if hash_match:
                    info_hash = hash_match.group(1)
        if not info_hash:
            return []
        return [StreamLink(url=_magnet(info_hash, item.title), quality="magnet")]


class ThePirateBaySource(Source):
    """The Pirate Bay - via RSS feed and apibay.org API."""

    id = "thepiratebay"
    name = "The Pirate Bay"
    category = "streams"

    BASE_URL = "https://thepiratebay.org"
    API_URL = "https://apibay.org/q.php?q={query}"
    RSS_URL = "https://thepiratebay.org/rss.php?q={query}"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        url = self.API_URL.format(query=urllib.parse.quote(query))

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with open_url(url, self.timeout, self.proxy_url, req.headers) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise SourceError(f"The Pirate Bay search failed: {exc}") from exc

        if not isinstance(data, list):
            return []

        results = []
        for item in data[: self.limit]:
            if not isinstance(item, dict):
                continue

            info_hash = item.get("info_hash", "")
            name = item.get("name", "")
            if not info_hash or not name:
                continue

            size = item.get("size", "")
            seeds = item.get("seeders", 0)
            leechers = item.get("leechers", 0)
            category = item.get("category", "")
            added = item.get("added", "")

            quality = _guess_resolution(name)
            year = _guess_year(name)

            kind = MediaKind.MOVIE
            cat_num = int(category) if category.isdigit() else 0
            # TPB categories: 200=video, 201=movies, 205=TV shows, 500=porn
            if cat_num in (205, 208):
                kind = MediaKind.SERIES
            elif cat_num in (500, 501):
                kind = MediaKind.ANIME  # adult anime

            size_str = f" {self._format_size(size)}" if size else ""
            seed_str = f" 👤{seeds}" if seeds else ""
            peer_str = f" 📥{leechers}" if leechers else ""

            results.append(
                SearchResult(
                    id=f"tpb:{info_hash}",
                    title=name,
                    kind=kind,
                    source_id=self.id,
                    year=year,
                    poster_url=None,
                    overview=f"{quality} · Added: {added}{size_str}{seed_str}{peer_str}",
                    genres=("torrent",),
                )
            )
        return results

    @staticmethod
    def _format_size(size_str: str) -> str:
        try:
            size = int(size_str)
        except (ValueError, TypeError):
            return size_str
        else:
            for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
                if size < 1024:
                    return f"{size:.1f}{unit}"
                size /= 1024
            return f"{size:.1f}PiB"

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        info_hash = item.id.split(":")[-1] if ":" in item.id else item.id
        if not info_hash or len(info_hash) != 40:
            return []
        return [StreamLink(url=_magnet(info_hash, item.title), quality="magnet")]


class RARBGMirrorSource(Source):
    """RARBG mirrors via torrentapi.org - additional endpoints."""

    id = "rarbg-mirror"
    name = "RARBG Mirrors (torrentapi.org)"
    category = "streams"

    # Multiple API endpoints for mirrors
    API_ENDPOINTS = [
        "https://torrentapi.org/pubapi_v2.php",
        "https://torrentapi.org/pubapi_v2.php",
    ]

    def __init__(
        self,
        api_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.api_url = (api_url or self.API_ENDPOINTS[0]).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit
        self._token: str | None = None
        self._app_id = "torrentio-tui-mirror"

    def _get_token(self) -> str:
        if self._token:
            return self._token
        url = f"{self.api_url}?get_token=get_token&app_id={urllib.parse.quote(self._app_id)}"
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict) or "token" not in data:
            raise SourceError("RARBG Mirror: failed to get token")
        self._token = str(data["token"])
        return self._token

    def _search_api(self, query: str, category: str = "") -> list[dict]:
        token = self._get_token()
        encoded_query = urllib.parse.quote(query.strip())
        cat_param = f"&category={category}" if category else ""
        url = (
            f"{self.api_url}?mode=search&search_string={encoded_query}"
            f"{cat_param}&format=json_extended&token={urllib.parse.quote(token)}"
            f"&app_id={urllib.parse.quote(self._app_id)}&limit={self.limit}"
        )
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict):
            raise SourceError("RARBG Mirror: unexpected response format")
        if data.get("error_code") == 20:
            self._token = None
            return self._search_api(query, category)
        if "error" in data:
            raise SourceError(f"RARBG Mirror API error: {data['error']}")
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
            info_hash = item.get("download") or item.get("info_hash")
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
                    id=f"rarbg-mirror:{info_hash}",
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
            raise SourceError(f"Bad RARBG Mirror id: {item.id}") from exc
        magnet = _magnet(info_hash, item.title)
        return [StreamLink(url=magnet, quality=item.title)]


class NyaaTorrentsSource(Source):
    """Additional Nyaa mirror - nyaa.si and alternatives."""

    id = "nyaa-torrents"
    name = "Nyaa Torrents (Mirrors)"
    category = "anime"

    MIRRORS = [
        "https://nyaa.si",
        "https://nyaa.iss.one",
        "https://sukebei.nyaa.si",
    ]

    NYAA_RSS = "{base}/?page=rss&q={query}&c=1_2&f=0"

    def __init__(
        self,
        mirror: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        self.base_url = (mirror or self.MIRRORS[0]).rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        url = self.NYAA_RSS.format(base=self.base_url, query=urllib.parse.quote(query))

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"},
            )
            with open_url(url, self.timeout, self.proxy_url, req.headers) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise SourceError(f"Nyaa mirror search failed: {exc}") from exc

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            desc = (desc_elem.text or "") if desc_elem is not None else ""
            pub_date = (pub_date_elem.text or "") if pub_date_elem is not None else ""

            size = ""
            seeds = ""
            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]iB)", desc)
            if size_match:
                size = size_match.group(1)
            seeds_match = re.search(r"Seeders:\s*(\d+)", desc)
            if seeds_match:
                seeds = f" 👤{seeds_match.group(1)}"

            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            quality = _guess_resolution(title)

            results.append(
                SearchResult(
                    id=f"nyaa-torrents:{link}",
                    title=clean_title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=f"{quality} · {pub_date} · {size}{seeds}",
                    genres=("anime",),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        if ":" not in item.id:
            return []
        _, url = item.id.split(":", 1)
        return [StreamLink(url=url, quality="torrent", is_live=False)]
