"""Torrent-index sources with real, keyless JSON APIs.

Unlike plain websites, these expose machine-readable endpoints, so they
return genuine playable magnets (resolved through the app's usual
webtorrent/peerflix bridge or a debrid-backed addon):

* YTS — official API (`yts.mx/api`), movies only.
* RARBG — backup API (`torrentapi.org`, token-based, rate-limited).

Both honor `network.proxy_url` via `torrentio_tui.proxy.open_url`.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
import urllib.error
import urllib.parse

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
    try:
        with open_url(url, timeout, proxy_url, headers) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except ProxyError as exc:
        raise SourceError(str(exc)) from exc
    except urllib.error.HTTPError as exc:
        raise SourceError(f"Request failed (HTTP {exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error for {url}: {exc.reason}") from exc
    except (json.JSONDecodeError, TimeoutError) as exc:
        raise SourceError(f"Bad response from {url}: {exc}") from exc


class YTSSource(Source):
    """YTS/YIFY movies via the official API — high-quality movie torrents
    as real magnets (movies only; series/anime return no results)."""

    id = "yts"
    name = "YTS / YIFY Movies"
    category = "streams"

    API = "https://yts.mx/api/v2"

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
    """RARBG index via the backup `torrentapi.org` API (token-based, the
    client throttles itself to the API's 1-request-per-2-seconds limit).
    Each result is one release; its magnet plays via the torrent bridge."""

    id = "rarbg"
    name = "RARBG (Torrent API)"
    category = "streams"

    API = "https://torrentapi.org/pubapi_v2.php"
    APP_ID = "torrentio-tui"

    def __init__(
        self,
        api_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 25,
    ) -> None:
        self.api_url = api_url or self.API
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit
        self._token: str | None = None
        self._token_at: float = 0.0
        self._last_call_at: float = 0.0
        self._cache: dict[str, list[dict]] = {}

    # -- rate limiting -------------------------------------------------
    def _throttle(self) -> None:
        wait = 2.0 - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        self._last_call_at = time.monotonic()

    def _call(self, params: dict[str, str]) -> dict:
        params = {**params, "app_id": self.APP_ID}
        if "get_token" not in params and self._token:
            params["token"] = self._token
        self._throttle()
        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        data = _read_json(url, self.timeout, self.proxy_url)
        if not isinstance(data, dict):
            raise SourceError("RARBG API returned an unexpected response")
        if "error" in data and "token" in params:
            # Token expired (15 min lifetime) — refresh once and retry.
            self._token = None
            self._ensure_token()
            params["token"] = self._token or ""
            self._throttle()
            url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
            data = _read_json(url, self.timeout, self.proxy_url)
            if not isinstance(data, dict):
                raise SourceError("RARBG API returned an unexpected response")
        if data.get("error"):
            raise SourceError(f"RARBG API error: {data['error']}")
        return data

    def _ensure_token(self) -> None:
        if self._token and time.monotonic() - self._token_at < 600:
            return
        data = self._call({"get_token": "get_token"})
        token = data.get("token")
        if not token:
            raise SourceError("RARBG API refused a token")
        self._token = str(token)
        self._token_at = time.monotonic()

    def _search_raw(self, query: str) -> list[dict]:
        if query in self._cache:
            return self._cache[query]
        self._ensure_token()
        data = self._call(
            {
                "mode": "search",
                "search_string": query,
                "format": "json_extended",
                "ranked": "0",
                "limit": str(self.limit),
            }
        )
        rows = data.get("torrent_results") or []
        rows = [r for r in rows if isinstance(r, dict)]
        self._cache[query] = rows
        return rows

    # -- Source ---------------------------------------------------------
    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results = []
        for index, row in enumerate(self._search_raw(query)):
            title = str(row.get("title", query))
            category = str(row.get("category", ""))
            lowered = category.lower()
            if lowered.startswith("tv") or "episode" in lowered:
                kind = MediaKind.SERIES
            elif "anime" in lowered:
                kind = MediaKind.ANIME
            else:
                kind = MediaKind.MOVIE
            results.append(
                SearchResult(
                    id=f"rarbg:{query}:{index}",
                    title=title,
                    kind=kind,
                    source_id=self.id,
                    year=_guess_year(title),
                    genres=(category,) if category else (),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        # One release == one synthetic episode carrying its magnet in id.
        try:
            _, query, index_s = item.id.split(":", 2)
            rows = self._search_raw(query)
            row = rows[int(index_s)]
        except (ValueError, IndexError, KeyError) as exc:
            raise SourceError(f"Bad RARBG id: {item.id}") from exc
        magnet = str(row.get("download", ""))
        if not magnet:
            return [Episode(id=item.id, title=item.title)]
        return [Episode(id=magnet, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        if not (episode.id.startswith("magnet:") or episode.id.startswith("http")):
            return []
        seeders = ""
        try:
            _, query, index_s = item.id.split(":", 2)
            row = self._search_raw(query)[int(index_s)]
            seeders = f" 👤{row.get('seeders', 0)}"
            size = f" 💾{row.get('size', '')}" if row.get("size") else ""
        except (ValueError, IndexError, KeyError):
            size = ""
        return [
            StreamLink(
                url=episode.id,
                quality=f"{_guess_resolution(item.title)}{seeders}{size}",
            )
        ]
