"""Extended adult content sources (opt-in, gated).

Adds support for:
- E-Hentai / ExHentai (hentai manga/doujinshi)
- Hitomi.la (hentai manga)
- HentaiHaven alternative (hentai anime streaming)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.adult import AdultSourceBase
from torrentio_tui.sources.base import SourceError

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"


def _ehentai_cover(gid: int, token: str, is_ex: bool = False) -> str:
    """Build thumbnail URL for E-Hentai/ExHentai."""
    domain = "exhentai.org" if is_ex else "ehentai.org"
    return f"https://{domain}/t/{token}/{gid}-1.jpg"


class EHentaiSource(AdultSourceBase):
    """E-Hentai / ExHentai - hentai manga/doujinshi catalogue."""

    id = "ehentai"
    name = "E-Hentai / ExHentai"

    EHENTAI_API = "https://api.e-hentai.org/api.php"
    EXHENTAI_API = "https://api.exhentai.org/api.php"

    def __init__(self, config: Config | None = None, use_ex: bool = False) -> None:
        super().__init__(config)
        self.use_ex = use_ex
        self.api_url = self.EXHENTAI_API if use_ex else self.EHENTAI_API

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        payload = {
            "method": "gdata",
            "gidlist": [],
            "namespace": 1,
            "search": query,
        }

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode(),
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise SourceError(f"E-Hentai search failed: {exc}") from exc

        results = []
        for gallery in data.get("gmetadata", []):
            if not isinstance(gallery, dict):
                continue
            gid = gallery.get("gid")
            token = gallery.get("token")
            title = gallery.get("title", "Unknown")
            title_jpn = gallery.get("title_jpn", "")
            category = gallery.get("category", "")
            tags = [t.split(":")[1] if ":" in t else t for t in gallery.get("tags", [])]
            thumb = _ehentai_cover(gid, token, self.use_ex) if gid and token else ""

            display_title = title
            if title_jpn:
                display_title += f" ({title_jpn})"

            results.append(
                SearchResult(
                    id=f"ehentai:{gid}:{token}",
                    title=display_title[:200],
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=thumb,
                    overview=f"Category: {category}",
                    genres=tuple(tags[:10]),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        parts = item.id.split(":")
        if len(parts) < 3:
            return []
        _, gid_str, token = parts[0], parts[1], parts[2]
        gid = int(gid_str)

        payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode(),
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        gallery = data.get("gmetadata", [{}])[0]
        files = gallery.get("files", [])

        links = []
        for i, file_info in enumerate(files):
            if not isinstance(file_info, dict):
                continue
            src = file_info.get("src", "")
            if src:
                links.append(
                    StreamLink(
                        url=src,
                        quality=f"Page {i + 1}",
                        headers={
                            "Referer": f"https://{'exhentai' if self.use_ex else 'ehentai'}.org/"
                        },
                    )
                )
        return links


class HitomiLaSource(AdultSourceBase):
    """Hitomi.la - hentai manga/doujinshi."""

    id = "hitomila"
    name = "Hitomi.la"

    HITOMI_API = "https://hitomi.la"

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.HITOMI_API}/search/{urllib.parse.quote(query)}.json"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise SourceError(f"Hitomi.la search failed: {exc}") from exc

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            gallery_id = item.get("id")
            title = item.get("title", "Unknown")
            artists = [a for a in item.get("artists", []) if isinstance(a, str)]
            tags = [t for t in item.get("tags", []) if isinstance(t, str)]
            lang = item.get("language", "")
            thumb = (
                f"https://ltn.hitomi.la/galleries/{gallery_id}/thumbs/0.jpg" if gallery_id else ""
            )

            results.append(
                SearchResult(
                    id=f"hitomila:{gallery_id}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=thumb,
                    overview=f"Language: {lang} | Artists: {', '.join(artists[:3])}",
                    genres=tuple(tags[:10]),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        gallery_id = item.id.split(":")[-1] if ":" in item.id else item.id

        url = f"{self.HITOMI_API}/galleries/{gallery_id}.js"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/javascript"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                content = resp.read().decode("utf-8")
        except Exception:
            return []

        # The response is JavaScript, we need to extract image URLs
        # Format: var galleryinfo = {...}; var files = [...];
        import re

        files_match = re.search(r"var\s+files\s*=\s*(\[.*?\]);", content, re.DOTALL)
        if not files_match:
            return []

        try:
            files = json.loads(files_match.group(1))
        except json.JSONDecodeError:
            return []

        links = []
        for i, file_info in enumerate(files):
            if not isinstance(file_info, dict):
                continue
            hash_val = file_info.get("hash", "")
            name = file_info.get("name", "")
            if not hash_val or not name:
                continue

            # Build CDN URL
            subdomain = hash_val[:2]
            img_url = f"https://{subdomain}.hitomi.la/galleries/{gallery_id}/{name}"

            links.append(
                StreamLink(
                    url=img_url,
                    quality=f"Page {i + 1}",
                    headers={"Referer": "https://hitomi.la/"},
                )
            )
        return links


class HentaiHavenSource(AdultSourceBase):
    """HentaiHaven / HentaiStream - hentai anime streaming (mirror sites)."""

    id = "hentaihaven"
    name = "HentaiHaven (Hentai Anime)"

    HENTAI_HAVEN_API = "https://hentaihaven.xxx/api"

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = f"{self.HENTAI_HAVEN_API}/search?q={urllib.parse.quote(query)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise SourceError(f"HentaiHaven search failed: {exc}") from exc

        results = []
        for item in data.get("results", []):
            if not isinstance(item, dict):
                continue
            slug = item.get("slug", "")
            title = item.get("title", "Unknown")
            cover = item.get("thumbnail", "")
            tags = [t.get("name", "") for t in item.get("tags", []) if isinstance(t, dict)]
            released = item.get("release_date", "")

            results.append(
                SearchResult(
                    id=f"hentaihaven:{slug}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=int(released[:4]) if released and released[:4].isdigit() else None,
                    poster_url=cover,
                    overview="",
                    genres=tuple(tags[:10]),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        self._check_enabled()
        if ":" not in item.id:
            return [Episode(id=item.id, title=item.title)]
        _, slug = item.id.split(":", 1)

        url = f"{self.HENTAI_HAVEN_API}/series/{slug}"

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
            if not isinstance(ep, dict):
                continue
            ep_slug = ep.get("slug", "")
            ep_title = ep.get("title", "")
            ep_num = ep.get("number", 0)
            episodes.append(Episode(id=f"hentaihaven:{ep_slug}", title=ep_title, number=ep_num))

        episodes.sort(key=lambda e: e.number or 0)
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        if ":" not in episode.id:
            return []
        _, ep_slug = episode.id.split(":", 1)

        url = f"{self.HENTAI_HAVEN_API}/episode/{ep_slug}/sources"

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
            if not isinstance(src, dict):
                continue
            stream_url = src.get("url", "")
            quality = src.get("quality", "auto")
            if stream_url:
                links.append(
                    StreamLink(
                        url=stream_url,
                        quality=quality,
                        headers={"Referer": "https://hentaihaven.xxx/"},
                    )
                )
        return links
