"""Adult content sources (opt-in, gated).

These sources are only available when explicitly enabled in config
AND the user confirms they are of legal age in their jurisdiction.
"""

from __future__ import annotations

import json
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
            if exc.code == 403:
                raise SourceError(f"Blocked (HTTP 403): {url}") from exc
            raise SourceError(f"HTTP {exc.code}: {url}") from exc
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
                # Check if adult content (genre or tag)
                genres = meta.get("genres") or meta.get("genre") or []
                is_adult = any(g.lower() in ("adult", "hentai", "erotic", "porn") for g in genres)

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

    def _parse_year(self, release_info: str | None) -> int | None:
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
    """Hanime.tv - hentai anime streaming."""

    id = "hanime"
    name = "Hanime.tv (Hentai Anime)"

    HANIME_API = "https://hanime.tv/api/v8"

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.HANIME_API}/search?keyword={urllib.parse.quote(query)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise SourceError(f"Hanime API error: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SourceError(f"Bad response: {exc}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        results = []
        for item in data.get("data", []):
            title = item.get("name", "")
            slug = item.get("slug", "")
            cover = item.get("cover_url", "")
            description = item.get("description", "")
            year = item.get("released_year")
            brands = item.get("brands", [])
            tags = [b.get("name", "") for b in brands if b.get("name")]

            results.append(
                SearchResult(
                    id=f"hanime:{slug}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=year,
                    poster_url=cover,
                    overview=description[:300] if description else "",
                    genres=tuple(tags),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        self._check_enabled()
        if ":" not in item.id:
            return [Episode(id=item.id, title=item.title)]
        _, slug = item.id.split(":", 1)

        # Fetch episodes for this show
        url = f"{self.HANIME_API}/anime/{slug}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return [Episode(id=item.id, title=item.title)]

        episodes = []
        for ep in data.get("episodes", []):
            ep_num = ep.get("number", 0)
            ep_title = ep.get("name") or f"Episode {ep_num}"
            ep_slug = ep.get("slug", "")
            episodes.append(Episode(id=f"hanime:{ep_slug}", title=ep_title, number=ep_num))

        episodes.sort(key=lambda e: e.number or 0)
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        if ":" not in episode.id:
            return []
        _, ep_slug = episode.id.split(":", 1)

        # Get stream URLs for this episode
        url = f"{self.HANIME_API}/video/embed?id={ep_slug}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        links = []
        for src in data.get("sources", []):
            stream_url = src.get("src", "")
            if not stream_url:
                continue
            quality = src.get("height", "auto")
            if quality != "auto":
                quality = f"{quality}p"
            links.append(
                StreamLink(
                    url=stream_url,
                    quality=quality,
                    headers={"Referer": "https://hanime.tv/"},
                )
            )
        return links


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
    """Rule34.xxx - adult artwork."""

    id = "rule34"
    name = "Rule34.xxx"

    RULE34_API = "https://api.rule34.xxx/index.php"

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.RULE34_API}?page=dapi&s=post&q=index&tags={urllib.parse.quote(query)}&json=1&limit=30"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise SourceError(f"Rule34 search failed: {exc}") from exc

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
            file_url = item.get("file_url", "")

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
