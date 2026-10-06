"""Extended adult content sources (opt-in, gated).

Adds support for:
- E-Hentai / ExHentai (hentai manga/doujinshi)
- Hitomi.la (hentai manga)
- Sukebei (Nyaa's adult tracker — hentai anime torrents)
"""

from __future__ import annotations

import json
import re
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
    EHENTAI_BASE = "https://e-hentai.org"
    EXHENTAI_BASE = "https://exhentai.org"

    #: Gallery links on the HTML search page: /g/<gid>/<token>/
    _GALLERY_LINK_RE = re.compile(r"/g/(\d+)/([0-9a-f]{10})/")

    def __init__(self, config: Config | None = None, use_ex: bool = False) -> None:
        super().__init__(config)
        self.use_ex = use_ex
        self.api_url = self.EXHENTAI_API if use_ex else self.EHENTAI_API
        self.base_url = self.EXHENTAI_BASE if use_ex else self.EHENTAI_BASE

    def _search_gallery_ids(self, query: str) -> list[tuple[int, str]]:
        """The `gdata` API only accepts explicit gid/token pairs — it has
        no free-text search (passing one returns "gdata request needs a
        gidlist"). So search the HTML index first and scrape the gallery
        links, then resolve metadata via `gdata`."""
        url = f"{self.base_url}/?f_search={urllib.parse.quote(query)}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceError(f"E-Hentai search failed (HTTP {code})") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"E-Hentai search failed: {exc}") from exc
        seen: list[tuple[int, str]] = []
        for gid_str, token in self._GALLERY_LINK_RE.findall(html):
            pair = (int(gid_str), token)
            if pair not in seen:
                seen.append(pair)
            if len(seen) >= 25:
                break
        return seen

    def search(self, query: str) -> list[SearchResult]:
        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        pairs = self._search_gallery_ids(query)
        if not pairs:
            return []

        payload = {
            "method": "gdata",
            "gidlist": [[gid, token] for gid, token in pairs],
            "namespace": 1,
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
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (403, 404):
                raise SourceError(
                    f"Hitomi.la search failed (HTTP {code}) — it serves "
                    "results through client-side indexes that block "
                    "automated clients. A proxy (network.proxy_url) "
                    "sometimes helps."
                ) from exc
            raise SourceError(f"Hitomi.la search failed (HTTP {code})") from exc
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


class SukebeiSource(AdultSourceBase):
    """Sukebei — Nyaa's adult tracker (hentai anime/manga torrents).

    Same RSS protocol as Nyaa.si (verified live), so results are real
    torrents that play through the torrent bridge (webtorrent/peerflix)
    with seeking inside the buffered pieces, or via a debrid-backed
    addon. Gated like every other adult source.
    """

    id = "sukebei"
    name = "Sukebei (Hentai Torrents)"

    RSS = "https://sukebei.nyaa.si/?page=rss&q={query}&f=0"

    def __init__(
        self,
        config: Config | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        limit: int = 20,
    ) -> None:
        super().__init__(config)
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.limit = limit

    def search(self, query: str) -> list[SearchResult]:
        from torrentio_tui.proxy import open_url
        from torrentio_tui.sources.torrent_extended import _guess_resolution

        self._check_enabled()
        query = query.strip()
        if not query:
            return []

        url = self.RSS.format(query=urllib.parse.quote(query))
        try:
            with open_url(url, self.timeout, self.proxy_url, {"User-Agent": _USER_AGENT}) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise SourceError(f"Sukebei search failed: {exc}") from exc

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item")[: self.limit]:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            if title_elem is None or link_elem is None:
                continue
            title = title_elem.text or ""
            link = (link_elem.text or "").strip()
            desc = (desc_elem.text or "") if desc_elem is not None else ""
            if not title or not link:
                continue
            size = ""
            seeds = ""
            size_match = re.search(r"Size:\s*([\d.]+\s*[GMK]iB)", desc)
            if size_match:
                size = size_match.group(1)
            seeds_match = re.search(r"Seeders:\s*(\d+)", desc)
            if seeds_match:
                seeds = f" 👤{seeds_match.group(1)}"
            clean_title = re.sub(r"\s+", " ", re.sub(r"\[.*?\]", "", title)).strip()
            quality = _guess_resolution(title)
            overview = " · ".join(p for p in (quality, size + seeds) if p)
            results.append(
                SearchResult(
                    id=f"sukebei:{link}",
                    title=clean_title or title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=overview,
                    genres=("hentai",),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        self._check_enabled()
        if ":" not in item.id:
            return []
        _, url = item.id.split(":", 1)
        if not url:
            return []
        return [StreamLink(url=url, quality="torrent", is_live=False)]
