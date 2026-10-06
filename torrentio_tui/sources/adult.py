"""Adult content sources (opt-in, gated).

These sources are only available when explicitly enabled in config
AND the user confirms they are of legal age in their jurisdiction.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.3 (+https://github.com/yubiiixtreme/torrentio-tui)"


# Check if adult content is allowed
def _adult_allowed(config: Config | None = None) -> bool:
    """Check if adult content is enabled in config."""
    if config is None:
        config = Config.load()
    return config.adult.enabled if hasattr(config, "adult") else False


def _bridge_by_title(
    config: Config, title: str, kind: MediaKind, source_id: str
) -> list[StreamLink]:
    """Resolve `title` to playable streams through the user's configured
    Stremio-protocol addon — the same bridge the catalogue companions
    (TVMaze, Jikan, ...) use for metadata-only entries."""
    from torrentio_tui.sources.stremio import StremioSource

    addon = StremioSource(
        cinemeta_url=config.stremio.cinemeta_url,
        stream_url=config.stremio.stream_url,
        timeout=config.stremio.timeout_seconds,
        proxy_url=config.network.proxy_url,
        source_id=f"{source_id}-bridge",
    )
    try:
        matches = addon.search(title)
    except SourceError as exc:
        raise SourceError(f"Could not resolve {title!r} for playback: {exc}") from exc
    wanted = {kind} | ({MediaKind.SERIES, MediaKind.MOVIE} if kind == MediaKind.ANIME else set())
    candidates = [m for m in matches if m.kind in wanted] or matches
    if not candidates:
        raise SourceError(
            f"{title!r} is metadata-only here — no playable match. "
            "Search the same title under a stream source (stremio, comet, ...)."
        )
    picked = candidates[0]
    return addon.get_streams(picked, Episode(id=picked.id, title=picked.title))


class AdultSourceBase(Source):
    """Base class for adult sources with age gating."""

    category = "adult"
    supports_live = False

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        if not _adult_allowed(self.config):
            raise SourceError(
                "Adult content is disabled. Enable it in config.toml: [adult] enabled = true"
            )

    def _check_enabled(self) -> None:
        if not _adult_allowed(self.config):
            raise SourceError("Adult content not enabled in config")


class StremioAdultSource(AdultSourceBase):
    """Stremio/Cinemeta with adult content enabled."""

    id = "stremio-adult"
    name = "Stremio Adult (Cinemeta + Torrentio)"

    def __init__(
        self,
        config: Config | None = None,
        cinemeta_url: str | None = None,
        stream_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        super().__init__(config)
        self.cinemeta_url = (cinemeta_url or "https://v3-cinemeta.strem.io").rstrip("/")
        self.stream_url = (stream_url or "https://torrentio.strem.fun").rstrip("/")
        self.timeout = timeout

    def _get_json(self, url: str) -> dict:
        import urllib.request

        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 403:
                raise SourceError(f"Blocked (HTTP 403): {url}") from exc
            raise SourceError(f"HTTP {code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SourceError(f"Bad JSON: {exc}") from exc

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        results = []
        # Search both movie and series catalogs
        for stype in ("movie", "series"):
            url = f"{self.cinemeta_url}/catalog/{stype}/top/search={urllib.parse.quote(query)}.json"
            try:
                data = self._get_json(url)
            except SourceError:
                continue

            for meta in data.get("metas", []) or []:
                tt = meta.get("id") or meta.get("imdb_id")
                if not tt:
                    continue
                genres = meta.get("genres") or meta.get("genre") or []

                # Include all results when adult is enabled
                results.append(
                    SearchResult(
                        id=f"{stype}:{tt}",
                        title=str(meta.get("name", tt)),
                        kind=MediaKind.MOVIE if stype == "movie" else MediaKind.SERIES,
                        source_id=self.id,
                        year=self._parse_year(meta.get("releaseInfo") or meta.get("year")),
                        poster_url=meta.get("poster"),
                        overview=meta.get("description"),
                        genres=tuple(str(g) for g in genres),
                    )
                )
        return results

    def _parse_year(self, release_info: str | int | None) -> int | None:
        if release_info is None:
            return None
        if isinstance(release_info, int):
            return release_info if 1000 <= release_info <= 9999 else None
        if not isinstance(release_info, str):
            try:
                release_info = str(release_info)
            except Exception:
                return None
        if not release_info:
            return None
        digits = "".join(c for c in release_info[:10] if c.isdigit())
        if len(digits) >= 4:
            try:
                return int(digits[:4])
            except ValueError:
                return None
        return None

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        self._check_enabled()
        stype, tt = item.id.split(":", 1)
        url = f"{self.cinemeta_url}/meta/{stype}/{tt}.json"
        data = self._get_json(url)
        meta = data.get("meta", {})
        videos = meta.get("videos") or []
        if stype == "movie" or not videos:
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

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        stype, tt = item.id.split(":", 1)
        stream_type = "movie" if stype == "movie" else "series"
        video_id = episode.id
        if ":" not in video_id or not video_id.startswith("tt"):
            video_id = tt
        url = f"{self.stream_url}/stream/{stream_type}/{video_id}.json"
        data = self._get_json(url)
        raw = data.get("streams", []) or []
        links = []
        for s in raw:
            name = str(s.get("name", ""))
            title = str(s.get("title", ""))
            if s.get("url"):
                links.append(
                    StreamLink(
                        url=str(s["url"]),
                        quality=name or "auto",
                        headers=dict(s.get("behaviorHints", {}).get("headers", {}) or {}),
                        subtitle_url=s.get("subtitles")
                        if isinstance(s.get("subtitles"), str)
                        else None,
                    )
                )
            elif s.get("infoHash"):
                import urllib.parse

                trackers = [
                    "udp://tracker.opentrackr.org:1337/announce",
                    "udp://open.tracker.cl:1337/announce",
                    "udp://tracker.openbittorrent.com:6969/announce",
                ]
                for t in s.get("sources", []) or []:
                    if t.startswith(("udp://", "http://", "https://")):
                        trackers.append(t)
                dn = urllib.parse.quote(f"{item.title} {title}".strip() or s["infoHash"])
                parts = [f"magnet:?xt=urn:btih:{s['infoHash']}", f"dn={dn}"]
                parts.extend(f"tr={urllib.parse.quote(t, safe='')}" for t in trackers)
                links.append(StreamLink(url="&".join(parts), quality=name or "magnet"))
        return links


class HanimeSource(AdultSourceBase):
    """Hanime.tv - hentai anime streaming catalogue.

    Search runs against hanime's public guest API (posters, tags,
    descriptions included); each entry is a single video, and playback
    resolves through the user's configured stream addon by title — the
    same bridge the catalogue companions (TVMaze, Jikan, ...) use —
    since hanime's own player handshake requires a browser session.
    """

    id = "hanime"
    name = "Hanime.tv (Hentai Anime)"

    SEARCH_API = "https://guest.freeanimehentai.net/api/v11/search_hvs"

    def _api_get(self, url: str) -> dict:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceError(f"Hanime API error: HTTP {code}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SourceError(f"Bad response: {exc}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc
        if not isinstance(data, dict):
            raise SourceError("Hanime API returned an unexpected response")
        return data

    @staticmethod
    def _plain_text(html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html or "")
        return re.sub(r"\s+", " ", text).strip()

    def _to_results(self, rows: object, limit: int) -> list[SearchResult]:
        if not isinstance(rows, list):
            return []
        results = []
        # The API ignores paging and can return thousands of rows —
        # cap client-side so the list stays usable.
        for item in rows[:limit]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("name", "") or "Unknown")
            slug = str(item.get("slug", "") or "")
            if not slug:
                continue
            poster = str(item.get("poster_url", "") or "")
            overview = self._plain_text(str(item.get("description", "") or ""))[:300]
            tags = [str(t) for t in item.get("tags", []) if isinstance(t, str)]
            brand = str(item.get("brand", "") or "")
            released = str(item.get("released_at", "") or "")
            year = int(released[:4]) if released[:4].isdigit() else None
            genres = ([brand] if brand else []) + tags

            results.append(
                SearchResult(
                    id=f"hanime:{slug}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=year,
                    poster_url=poster or None,
                    overview=overview,
                    genres=tuple(genres[:10]),
                )
            )
        return results

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = (
            f"{self.SEARCH_API}?search_text={urllib.parse.quote(query)}"
            "&order_by=likes&ordering=desc&page=0"
        )
        data = self._api_get(url)
        return self._to_results(data.get("data"), 40)

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        self._check_enabled()
        # Every catalogue entry is a single video — one synthetic episode
        # keeps the uniform pick-episode-then-play flow working.
        return [Episode(id=item.id, title=item.title)]

    def trending(self, limit: int = 20) -> list[SearchResult]:
        """Most-liked videos: the API ignores paging and returns the
        catalogue likes-first, so the front slice is the chart."""
        self._check_enabled()
        url = f"{self.SEARCH_API}?search_text=&order_by=likes&ordering=desc&page=0"
        data = self._api_get(url)
        return self._to_results(data.get("data"), limit)

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        return _bridge_by_title(
            self.config,
            item.title,
            MediaKind.ANIME,
            source_id=self.id,
        )


def _nhentai_year(upload_date: object) -> int | None:
    """The NHentai API returns `upload_date` as a unix timestamp (int),
    not a date string — handle both shapes."""
    if isinstance(upload_date, (int, float)):
        try:
            import datetime

            return datetime.datetime.fromtimestamp(upload_date, tz=datetime.timezone.utc).year
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(upload_date, str) and len(upload_date) >= 4 and upload_date[:4].isdigit():
        return int(upload_date[:4])
    return None


def _nhentai_cover(item: dict) -> str:
    """Build a thumbnail URL from the real API fields (`images.thumbnail`
    + `media_id`); the API has no `cover_image` field."""
    images = item.get("images", {})
    thumb = images.get("thumbnail", {}) if isinstance(images, dict) else {}
    t = thumb.get("t", "j") if isinstance(thumb, dict) else "j"
    ext = {"j": "jpg", "p": "png", "w": "webp"}.get(t, "jpg")
    media_id = item.get("media_id", "")
    if not media_id:
        return ""
    return f"https://t.nhentai.net/galleries/{media_id}/thumb.{ext}"


class NHentaiSource(AdultSourceBase):
    """NHentai - hentai manga/doujinshi."""

    id = "nhentai"
    name = "NHentai"

    NHENTAI_API = "https://nhentai.net/api"

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.NHENTAI_API}/gallery/search?q={urllib.parse.quote(query)}&page=1"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 403:
                raise SourceError(
                    "NHentai blocked the request (HTTP 403) — it filters "
                    "datacenter/VPN IPs. Try setting network.proxy_url "
                    "(e.g. Cloudflare WARP's proxy mode)."
                ) from exc
            raise SourceError(f"NHentai search failed (HTTP {code})") from exc
        except Exception as exc:
            raise SourceError(f"NHentai search failed: {exc}") from exc

        results = []
        for item in data.get("result", []):
            if not isinstance(item, dict):
                continue
            title_dict = item.get("title", {})
            if not isinstance(title_dict, dict):
                title_dict = {}
            title = (
                title_dict.get("english")
                or title_dict.get("japanese")
                or title_dict.get("pretty", "")
            )
            cover = _nhentai_cover(item)
            tags = [t.get("name", "") for t in item.get("tags", []) if isinstance(t, dict)]
            year = _nhentai_year(item.get("upload_date"))

            results.append(
                SearchResult(
                    id=f"nhentai:{item.get('id', '')}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=year,
                    poster_url=cover,
                    overview="",
                    genres=tuple(tags),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        gallery_id = item.id.split(":")[-1] if ":" in item.id else item.id

        try:
            url = f"{self.NHENTAI_API}/gallery/{gallery_id}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        gallery = data.get("gallery", {})
        images = gallery.get("images", {})
        pages = images.get("pages", [])

        links = []
        for i, page in enumerate(pages):
            t = page.get("t", "j")
            ext = "jpg" if t == "j" else "png" if t == "p" else "webp"
            url = f"https://i.nhentai.net/galleries/{gallery.get('media_id', '')}/{i + 1}.{ext}"
            links.append(
                StreamLink(
                    url=url,
                    quality=f"Page {i + 1}",
                    headers={"Referer": "https://nhentai.net/"},
                )
            )
        return links


class Rule34Source(AdultSourceBase):
    """Rule34.xxx - adult artwork.

    The API now requires free credentials for most calls: put them in
    `[sources.rule34]` as `api_key` + `user_id` (from rule34.xxx's API
    page while logged in). Without them, searches raise a clear error
    instead of failing silently.
    """

    id = "rule34"
    name = "Rule34.xxx"

    RULE34_API = "https://api.rule34.xxx/index.php"

    def __init__(self, config: Config | None = None) -> None:
        super().__init__(config)
        src_cfg = self.config.sources_config.get("rule34", {})
        self.api_key = str(src_cfg.get("api_key", "") or "")
        self.user_id = str(src_cfg.get("user_id", "") or "")

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.RULE34_API}?page=dapi&s=post&q=index&tags={urllib.parse.quote(query)}&json=1&limit=30"
        if self.api_key and self.user_id:
            url += f"&api_key={urllib.parse.quote(self.api_key)}&user_id={urllib.parse.quote(self.user_id)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403):
                raise SourceError(
                    "Rule34.xxx rejected the request (HTTP "
                    f"{code}) — it now requires free API credentials: set "
                    "[sources.rule34] api_key + user_id in config.toml "
                    "(see rule34.xxx while logged in)."
                ) from exc
            raise SourceError(f"Rule34 search failed (HTTP {code})") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"Rule34 search failed: {exc}") from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            if "auth" in body.lower():
                raise SourceError(
                    "Rule34.xxx requires free API credentials for this call: "
                    "set [sources.rule34] api_key + user_id in config.toml."
                ) from exc
            raise SourceError(f"Rule34 search failed: bad response") from exc

        if isinstance(data, dict):
            # Error payloads come back as a dict, not a list.
            raise SourceError(f"Rule34 error: {data.get('error', data)}")
        if not isinstance(data, list):
            raise SourceError(f"Rule34 unexpected response: {type(data).__name__}")

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            tags = item.get("tags", "").split(" ")
            preview = item.get("preview_url", "")

            results.append(
                SearchResult(
                    id=f"rule34:{item.get('id', '')}",
                    title=item.get("tags", "Untitled")[:100],
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=preview,
                    overview="",
                    genres=tuple(tags[:10]),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        gallery_id = item.id.split(":")[-1] if ":" in item.id else item.id

        try:
            url = f"{self.RULE34_API}?page=dapi&s=post&q=index&id={gallery_id}&json=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        if not isinstance(data, list):
            return []
        links = []
        for item in data:
            if not isinstance(item, dict):
                continue
            file_url = item.get("file_url", "")
            if file_url:
                links.append(
                    StreamLink(
                        url=file_url,
                        quality="Original",
                        headers={"Referer": "https://rule34.xxx/"},
                    )
                )
        return links
