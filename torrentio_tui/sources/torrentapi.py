"""Torrent-index sources with real, keyless JSON APIs.

YTS exposes its official API (movies only) — search returns genuine
playable magnets, resolved through the app's usual webtorrent/peerflix
bridge or a debrid-backed addon. Honors `network.proxy_url` via
`torrentio_tui.proxy.open_url`.
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
