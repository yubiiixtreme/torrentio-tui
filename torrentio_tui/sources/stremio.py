"""Stremio-compatible source: Cinemeta catalogue + Torrentio-style streams.

How it fits together (standard Stremio pattern):

* **Catalogue/search** comes from Cinemeta (free metadata addon):
  ``{cinemeta}/catalog/{movie,series}/top/search={query}.json``
  and episode lists from ``{cinemeta}/meta/{type}/{tt}.json``.
* **Streams** come from a Stremio *stream* addon speaking the same
  ``/stream/{type}/{videoId}.json`` protocol — Torrentio by default
  (``https://torrentio.strem.fun``), but any compatible addon works
  (MediaFusion, Knightcrawler, a self-hosted Torrentio, ...).

Configure it (env vars win over ``config.toml``)::

    # ~/.config/torrentio-tui/config.toml
    [sources]
    enabled = ["stremio", "local"]

    [sources.stremio]
    cinemeta_url = "https://v3-cinemeta.strem.io"
    # Paste your *configured* addon URL from e.g.
    # https://torrentio.strem.fun/configure (it embeds providers + debrid key).
    stream_url = "https://torrentio.strem.fun"

    # or via env:
    # TORRENTIO_TUI_CINEMETA_URL, TORRENTIO_TUI_STREAM_URL, TORRENTIO_TUI_TIMEOUT

Torrentio Cloudflare-blocks some datacenter/VPN IP ranges (HTTP 403). If
you hit that, route requests through a proxy instead — see
``torrentio_tui/proxy.py`` and the ``[network] proxy_url`` config option
(e.g. Cloudflare WARP's local proxy mode).

Playback notes:

* If your stream addon returns direct ``http(s)`` URLs (typical when a
  RealDebrid/AllDebrid/Premiumize key is configured in the addon URL),
  mpv/vlc play them directly.
* Otherwise the addon returns ``infoHash`` magnets. mpv/vlc cannot play
  magnets natively, so the player backends hand them to a local torrent
  streamer if one is installed (``webtorrent`` / ``peerflix``). Install
  one of those, or configure a debrid key for direct links.

Legal note: only use this against content you have the right to access.
Torrentio-style addons scrape third-party torrents; pointing this source
at them to fetch infringing copies may violate copyright law and/or the
sites' terms. That choice — and any debrid keys / self-hosting — is yours.
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, build_opener, socks_proxy
from torrentio_tui.sources.base import Source, SourceError

DEFAULT_CINEMETA_URL = "https://v3-cinemeta.strem.io"
DEFAULT_STREAM_URL = "https://torrentio.strem.fun"

# Public trackers used when an addon returns infoHash without sources.
DEFAULT_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
]

_USER_AGENT = "torrentio-tui/0.2 (+https://github.com/yubiiixtreme/torrentio-tui)"


def _get_json(url: str, timeout: float, proxy_url: str | None = None) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    scheme = urllib.parse.urlsplit(proxy_url).scheme.lower() if proxy_url else ""
    try:
        with socks_proxy(proxy_url):
            # Only build a dedicated opener when an http(s) proxy is actually
            # configured; otherwise use urlopen() directly (also what tests
            # patch). A socks5:// proxy needs no opener — socks_proxy() above
            # routes the plain urlopen() call through it at the socket level.
            opener_open = build_opener(proxy_url).open if scheme in ("http", "https") else None
            response_cm = (
                opener_open(req, timeout=timeout)
                if opener_open
                else urllib.request.urlopen(req, timeout=timeout)
            )
            with response_cm as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
    except ProxyError as exc:
        raise SourceError(str(exc)) from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and "torrentio" in url.lower():
            hint = (
                "Already routed through your configured proxy — try a different "
                "one, or self-host Torrentio"
                if proxy_url
                else "Try setting network.proxy_url (e.g. Cloudflare WARP's local "
                "proxy mode) in config.toml, self-host Torrentio, or point "
                "stream_url at a compatible addon (MediaFusion/Knightcrawler)"
            )
            raise SourceError(
                f"Torrentio blocked this request (HTTP 403 — Cloudflare often "
                f"blocks datacenter/VPN IPs). {hint}."
            ) from exc
        raise SourceError(f"Request failed ({exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error for {url}: {exc.reason}") from exc
    except (json.JSONDecodeError, TimeoutError) as exc:
        raise SourceError(f"Bad response from {url}: {exc}") from exc


def _parse_year(release_info: str | None) -> int | None:
    if not release_info:
        return None
    digits = "".join(c for c in release_info[:10] if c.isdigit())
    if len(digits) >= 4:
        try:
            return int(digits[:4])
        except ValueError:
            return None
    return None


def _classify_kind(stremio_type: str, genres: list[str] | None) -> MediaKind:
    genre_set = {g.lower() for g in (genres or [])}
    if "anime" in genre_set or ("animation" in genre_set and stremio_type in ("series", "movie")):
        # Keep it visible as anime in the UI; wire format stays movie/series.
        return MediaKind.ANIME
    if stremio_type == "series":
        return MediaKind.SERIES
    return MediaKind.MOVIE


def _encode_id(stremio_type: str, tt_id: str) -> str:
    return f"{stremio_type}:{tt_id}"


def _decode_id(item_id: str) -> tuple[str, str]:
    if ":" in item_id and item_id.split(":")[0] in ("movie", "series"):
        stype, tt = item_id.split(":", 1)
        return stype, tt
    # Back-compat: bare tt ids (old history entries) default to movie.
    return "movie", item_id


def _quality_rank(text: str) -> int:
    t = text.lower()
    for token, rank in (
        ("2160", 50),
        ("4k", 50),
        ("1080", 40),
        ("720", 30),
        ("480", 20),
        ("cam", 5),
        ("scr", 6),
        ("ts", 6),
    ):
        if token in t:
            return rank
    return 25


def _parse_quality(name: str, title: str) -> str:
    """Build a compact human label like '1080p BluRay 👤120 💾1.8GB'."""
    blob = f"{name}\n{title}"
    quality = "auto"
    for token in ("2160p", "4K", "1080p", "720p", "480p", "CAM", "SCR", "TS"):
        if token.lower() in blob.lower():
            quality = token
            break
    extras: list[str] = []
    low = blob.lower()
    for tag in ("bluray", "web-dl", "webrip", "hdtv", "hdr", "dolby", "x265", "x264"):
        if tag in low:
            extras.append(tag.upper())
            if len(extras) >= 2:
                break
    # Seeders "👤 123" and size "💾 1.8 GB" appear in Torrentio titles.
    import re

    m = re.search(r"👤\s*(\d+)", blob)
    seeds = f" 👤{m.group(1)}" if m else ""
    m = re.search(r"💾\s*([\d.]+\s*[GM]B)", blob)
    size = f" 💾{m.group(1)}" if m else ""
    label = quality
    if extras:
        label += " " + " ".join(extras)
    return (label + seeds + size).strip()


def _build_magnet(info_hash: str, name: str, sources: list[str] | None) -> str:
    trackers = list(sources) if sources else []
    # Addon `sources` are usually already tracker URLs; keep http(s)/udp ones.
    trackers = [t for t in trackers if t.startswith(("udp://", "http://", "https://"))]
    for t in DEFAULT_TRACKERS:
        if t not in trackers:
            trackers.append(t)
    dn = urllib.parse.quote(name or info_hash)
    parts = [f"magnet:?xt=urn:btih:{info_hash}", f"dn={dn}"]
    parts.extend(f"tr={urllib.parse.quote(t, safe='')}" for t in trackers)
    return "&".join(parts)


class StremioSource(Source):
    """Cinemeta catalogue + Stremio-protocol streams (Torrentio default)."""

    id = "stremio"
    name = "Stremio (Cinemeta + Torrentio)"

    def __init__(
        self,
        cinemeta_url: str | None = None,
        stream_url: str | None = None,
        timeout: float = 15.0,
        max_results: int = 40,
        proxy_url: str | None = None,
    ) -> None:
        # Precedence: env vars > explicit args (config.toml) > defaults.
        self.cinemeta_url = (
            os.environ.get("TORRENTIO_TUI_CINEMETA_URL") or cinemeta_url or DEFAULT_CINEMETA_URL
        ).rstrip("/")
        raw_stream = (
            (os.environ.get("TORRENTIO_TUI_STREAM_URL") or stream_url or DEFAULT_STREAM_URL)
            .strip()
            .rstrip("/")
        )
        # Accept a pasted /manifest.json or /configure URL gracefully.
        if raw_stream.endswith("/manifest.json"):
            raw_stream = raw_stream[: -len("/manifest.json")]
        if raw_stream.endswith("/configure"):
            raw_stream = raw_stream[: -len("/configure")]
        self.stream_url = raw_stream
        try:
            self.timeout = float(os.environ.get("TORRENTIO_TUI_TIMEOUT", timeout))
        except ValueError:
            self.timeout = 15.0
        self.max_results = max_results
        self.proxy_url = os.environ.get("TORRENTIO_TUI_PROXY") or proxy_url or None

    # -- catalogue ------------------------------------------------------
    def _catalog(self, stremio_type: str, query: str) -> list[dict]:
        if query:
            extra = f"search={urllib.parse.quote(query)}"
            url = f"{self.cinemeta_url}/catalog/{stremio_type}/top/{extra}.json"
        else:
            url = f"{self.cinemeta_url}/catalog/{stremio_type}/top.json"
        try:
            data = _get_json(url, self.timeout, self.proxy_url)
        except SourceError:
            if query:
                raise
            return []
        return data.get("metas", []) or []

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results: list[SearchResult] = []
        errors: list[str] = []
        for stremio_type in ("movie", "series"):
            try:
                metas = self._catalog(stremio_type, query)
            except SourceError as exc:
                errors.append(str(exc))
                continue
            for meta in metas:
                tt = meta.get("id") or meta.get("imdb_id")
                if not tt:
                    continue
                raw_genres = meta.get("genres") or meta.get("genre") or []
                kind = _classify_kind(stremio_type, raw_genres)
                results.append(
                    SearchResult(
                        id=_encode_id(stremio_type, tt),
                        title=str(meta.get("name", tt)),
                        kind=kind,
                        source_id=self.id,
                        year=_parse_year(meta.get("releaseInfo") or meta.get("year")),
                        poster_url=meta.get("poster"),
                        overview=meta.get("description"),
                        genres=tuple(str(g) for g in raw_genres),
                    )
                )
                if len(results) >= self.max_results:
                    break
            if len(results) >= self.max_results:
                break
        if not results and errors:
            raise SourceError(" | ".join(errors))
        return results[: self.max_results]

    # -- episodes --------------------------------------------------------
    def get_episodes(self, item: SearchResult) -> list[Episode]:
        stremio_type, tt = _decode_id(item.id)
        url = f"{self.cinemeta_url}/meta/{stremio_type}/{tt}.json"
        data = _get_json(url, self.timeout, self.proxy_url)
        meta = data.get("meta", {})
        videos = meta.get("videos") or []
        if stremio_type == "movie" or not videos:
            return [Episode(id=item.id, title=item.title)]
        episodes = []
        for v in videos:
            vid = v.get("id", tt)
            title = v.get("name") or v.get("title") or vid
            try:
                season = int(v["season"]) if v.get("season") is not None else None
            except (ValueError, TypeError):
                season = None
            try:
                number = (
                    int(v.get("number", v.get("episode")))
                    if v.get("number", v.get("episode")) is not None
                    else None
                )
            except (ValueError, TypeError):
                number = None
            episodes.append(Episode(id=str(vid), title=str(title), season=season, number=number))
        episodes.sort(key=lambda e: (e.season or 0, e.number or 0))
        return episodes or [Episode(id=item.id, title=item.title)]

    # -- streams ----------------------------------------------------------
    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        stremio_type, tt = _decode_id(item.id)
        stream_type = "movie" if stremio_type == "movie" else "series"
        video_id = episode.id
        if ":" not in video_id or not video_id.startswith("tt"):
            # Episode ids are full video ids ("tt...:s:e"); fall back to tt.
            video_id = tt if stremio_type == "movie" else episode.id
            if ":" not in video_id:
                video_id = tt if stremio_type == "movie" else f"{tt}"
                # For series the API needs season/episode; if we only have
                # the series id the addon returns season packs / latest.
                if stremio_type == "series" and ":" not in episode.id and episode.id != item.id:
                    video_id = episode.id
        url = f"{self.stream_url}/stream/{stream_type}/{video_id}.json"
        data = _get_json(url, self.timeout, self.proxy_url)
        raw = data.get("streams", []) or []
        links: list[tuple[int, int, StreamLink]] = []
        for s in raw:
            name = str(s.get("name", ""))
            title = str(s.get("title", ""))
            label_src = f"{name}\n{title}"
            seeds = 0
            import re

            m = re.search(r"👤\s*(\d+)", label_src)
            if m:
                try:
                    seeds = int(m.group(1))
                except ValueError:
                    seeds = 0
            quality = _parse_quality(name, title)
            if s.get("url"):
                links.append(
                    (
                        _quality_rank(label_src),
                        seeds,
                        StreamLink(
                            url=str(s["url"]),
                            quality=quality or "auto",
                            headers=dict(s.get("behaviorHints", {}).get("headers", {}) or {}),
                            subtitle_url=s.get("subtitles")
                            if isinstance(s.get("subtitles"), str)
                            else None,
                        ),
                    )
                )
            elif s.get("infoHash"):
                magnet = _build_magnet(
                    str(s["infoHash"]), f"{item.title} {title}".strip(), s.get("sources")
                )
                if s.get("fileIdx") is not None:
                    # Largest-file autoplay covers most cases; keep the
                    # index visible so advanced users can pick files.
                    with contextlib.suppress(ValueError, TypeError):
                        quality += f" [f{int(s['fileIdx'])}]"
                links.append(
                    (
                        _quality_rank(label_src),
                        seeds,
                        StreamLink(url=magnet, quality=quality or "magnet"),
                    )
                )
            elif s.get("magnetUrl"):
                links.append(
                    (
                        _quality_rank(label_src),
                        seeds,
                        StreamLink(url=str(s["magnetUrl"]), quality=quality or "magnet"),
                    )
                )
        links.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [link for _, _, link in links]
