"""Extended anime sources: additional anime torrent and release sites.

Adds support for:
- AniDex (anime torrents via RSS)
- Anime Tosho (anime releases via RSS)
- Tokyo Toshokan (anime releases via RSS)
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"


def _fetch_rss(url: str, query: str | None = None) -> ET.Element:
    """Fetch and parse RSS/Atom feed."""
    if query:
        url = url.format(query=urllib.parse.quote(query))

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise SourceError(f"RSS fetch error: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SourceError(f"Timeout: {exc}") from exc

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise SourceError(f"Bad RSS/Atom response: {exc}") from exc

    return root


def _extract_quality(title: str) -> str:
    """Extract quality from title."""
    for q in ("2160p", "1080p", "720p", "480p", "4K", "4k"):
        if q.lower() in title.lower():
            return q
    return "auto"


def _extract_seeds_peers(text: str) -> tuple[str, str]:
    """Extract seeders and leechers from text."""
    seeds = ""
    peers = ""
    seed_match = re.search(r"(?:Seeders?|S):\s*(\d+)", text, re.IGNORECASE)
    peer_match = re.search(r"(?:Leechers?|Peers?|L):\s*(\d+)", text, re.IGNORECASE)
    if seed_match:
        seeds = f" 👤{seed_match.group(1)}"
    if peer_match:
        peers = f" 📥{peer_match.group(1)}"
    return seeds, peers


class AniDexSource(Source):
    """AniDex - anime torrents via RSS feed."""

    id = "anidex"
    name = "AniDex (Anime Torrents)"
    category = "anime"

    ANIDEX_RSS = "https://anidex.info/rss.php?q={query}&c=0&g=0"

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        root = _fetch_rss(self.ANIDEX_RSS, query)

        results = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")
            enclosure_elem = item.find("enclosure")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            desc = (desc_elem.text or "") if desc_elem is not None else ""
            pub_date = (pub_date_elem.text or "") if pub_date_elem is not None else ""

            size = ""
            if enclosure_elem is not None:
                length = enclosure_elem.get("length")
                if length and length.isdigit():
                    size = f" {int(int(length) / 1024 / 1024)} MiB"

            seeds, peers = _extract_seeds_peers(desc)

            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            quality = _extract_quality(title)

            results.append(
                SearchResult(
                    id=f"anidex:{link}",
                    title=clean_title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=f"{quality} · {pub_date}{size}{seeds}{peers}",
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


class AnimeToshoSource(Source):
    """Anime Tosho - anime releases via RSS feed."""

    id = "animetosho"
    name = "Anime Tosho (Anime Releases)"
    category = "anime"

    ANIME_TOSHO_RSS = "https://animetosho.org/rss?q={query}"

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        root = _fetch_rss(self.ANIME_TOSHO_RSS, query)

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
            seeds, peers = _extract_seeds_peers(desc)

            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            quality = _extract_quality(title)

            results.append(
                SearchResult(
                    id=f"animetosho:{link}",
                    title=clean_title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=f"{quality} · {pub_date} · {size}{seeds}{peers}",
                    genres=("anime", "release"),
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


class TokyoToshokanSource(Source):
    """Tokyo Toshokan - anime releases via RSS feed."""

    id = "tokyotoshokan"
    name = "Tokyo Toshokan (Anime Releases)"
    category = "anime"

    TOKYO_TOSHOKAN_RSS = "https://www.tokyotosho.info/rss.php?q={query}&c=1&f=0"

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        root = _fetch_rss(self.TOKYO_TOSHOKAN_RSS, query)

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
            seeds, peers = _extract_seeds_peers(desc)

            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            quality = _extract_quality(title)

            results.append(
                SearchResult(
                    id=f"tokyotoshokan:{link}",
                    title=clean_title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=f"{quality} · {pub_date} · {size}{seeds}{peers}",
                    genres=("anime", "release"),
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
