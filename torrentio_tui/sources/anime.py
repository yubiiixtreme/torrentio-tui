"""Anime-specific sources: specialized search for anime content.

Adds support for:
- AniList (GraphQL API) for anime metadata
- Nyaa.si for anime torrents
- SubsPlease for latest anime releases
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.3 (+https://github.com/yubiiixtreme/torrentio-tui)"

# AniList GraphQL API
ANILIST_URL = "https://graphql.anilist.co"

# AniList search query
ANILIST_SEARCH_QUERY = """
query ($search: String, $page: Int, $perPage: Int, $type: MediaType, $format: MediaFormat, $status: MediaStatus, $season: MediaSeason, $seasonYear: Int, $genre: String, $tag: String, $id: Int, $idMal: Int, $startDate: FuzzyDateInt, $endDate: FuzzyDateInt, $onList: Boolean, $isAdult: Boolean) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
      perPage
    }
    media(search: $search, type: $type, format: $format, status: $status, season: $season, seasonYear: $seasonYear, genre: $genre, tag: $tag, id: $id, idMal: $idMal, startDate: $startDate, endDate: $endDate, onList: $onList, isAdult: $isAdult, sort: [SEARCH_MATCH, POPULARITY_DESC]) {
      id
      idMal
      title {
        romaji
        english
        native
      }
      type
      format
      status
      description
      startDate {
        year
      }
      endDate {
        year
      }
      season
      seasonYear
      genres
      tags {
        name
        isAdult
      }
      averageScore
      popularity
      episodes
      duration
      countryOfOrigin
      source
      trailer {
        id
        site
        thumbnail
      }
      coverImage {
        extraLarge
        large
        medium
        color
      }
      bannerImage
      nextAiringEpisode {
        airingAt
        timeUntilAiring
        episode
      }
      isAdult
      isLicensed
    }
  }
}
"""

# Nyaa.si search (RSS)
NYAA_SEARCH_URL = "https://nyaa.si/?page=rss&q={query}&c=1_2&f=0"


@dataclass
class AnilistMedia:
    id: int
    title_romaji: str
    title_english: str | None
    title_native: str
    type: str  # ANIME, MANGA
    format: str | None  # TV, MOVIE, OVA, etc.
    status: str | None
    description: str | None
    year: int | None
    season: str | None
    season_year: int | None
    genres: list[str]
    average_score: int | None
    episodes: int | None
    cover_image: str | None
    is_adult: bool


def _fetch_anilist(query: str, is_adult: bool = False) -> list[AnilistMedia]:
    """Search AniList for anime."""
    variables = {
        "search": query,
        "page": 1,
        "perPage": 20,
        "type": "ANIME",
        "isAdult": is_adult,
    }

    payload = json.dumps({"query": ANILIST_SEARCH_QUERY, "variables": variables}).encode()

    try:
        req = urllib.request.Request(
            ANILIST_URL,
            data=payload,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise SourceError(f"AniList API error: HTTP {code}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SourceError(f"Bad response from AniList: {exc}") from exc
    except TimeoutError as exc:
        raise SourceError(f"Timeout: {exc}") from exc

    if "errors" in data:
        raise SourceError(f"AniList errors: {data['errors']}")

    media_list = []
    for m in data.get("data", {}).get("Page", {}).get("media", []):
        title = m.get("title", {})
        cover = m.get("coverImage", {})
        start_date = m.get("startDate", {})
        media_list.append(
            AnilistMedia(
                id=m["id"],
                title_romaji=title.get("romaji", ""),
                title_english=title.get("english"),
                title_native=title.get("native", ""),
                type=m.get("type", "ANIME"),
                format=m.get("format"),
                status=m.get("status"),
                description=m.get("description"),
                year=start_date.get("year"),
                season=m.get("season"),
                season_year=m.get("seasonYear"),
                genres=m.get("genres", []),
                average_score=m.get("averageScore"),
                episodes=m.get("episodes"),
                cover_image=cover.get("extraLarge") or cover.get("large"),
                is_adult=m.get("isAdult", False),
            )
        )
    return media_list


class AnilistSource(Source):
    """Search anime via AniList GraphQL API."""

    id = "anilist"
    name = "AniList (Anime Metadata)"
    category = "catalogue"

    def __init__(self, include_adult: bool = False) -> None:
        self.include_adult = include_adult

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        media_list = _fetch_anilist(query, is_adult=self.include_adult)

        results = []
        for m in media_list:
            # Build title
            title = m.title_english or m.title_romaji or m.title_native
            # Build overview
            parts = []
            if m.format:
                parts.append(m.format)
            if m.status:
                parts.append(m.status)
            if m.episodes:
                parts.append(f"{m.episodes} eps")
            if m.average_score:
                parts.append(f"⭐ {m.average_score}%")
            overview = " · ".join(parts)
            if m.description:
                # Strip HTML tags from description
                import re

                desc = re.sub(r"<[^>]+>", "", m.description)
                overview += f"\n{desc[:200]}..."

            results.append(
                SearchResult(
                    id=f"anilist:{m.id}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=m.year,
                    poster_url=m.cover_image,
                    overview=overview,
                    genres=tuple(m.genres),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        """Parse AniList ID and return episodes."""
        # item.id format: "anilist:12345"
        if ":" not in item.id:
            return [Episode(id=item.id, title=item.title)]
        _, anilist_id = item.id.split(":", 1)

        # For now, return synthetic episodes - could fetch actual episode list from AniList
        # This would require another GraphQL query
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """AniList is metadata only - no streams. Use with Torrentio/MediaFusion."""
        return []


class NyaaSource(Source):
    """Search anime torrents via Nyaa.si RSS."""

    id = "nyaa"
    name = "Nyaa.si (Anime Torrents)"
    category = "anime"

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        url = NYAA_SEARCH_URL.format(query=urllib.parse.quote(query))

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceError(f"Nyaa.si error: HTTP {code}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        # Parse RSS XML
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

            # Extract size, seeds, peers from description
            size = ""
            seeds = ""
            import re

            size_match = re.search(r"Size:\s*([\d.]+\s*[GM]iB)", desc)
            if size_match:
                size = size_match.group(1)
            seeds_match = re.search(r"Seeders:\s*(\d+)", desc)
            if seeds_match:
                seeds = f" 👤{seeds_match.group(1)}"

            # Clean title - remove batch/size info
            clean_title = re.sub(r"\[.*?\]", "", title).strip()
            clean_title = re.sub(r"\s+", " ", clean_title)

            quality = "auto"
            for q in ("1080p", "720p", "480p", "2160p", "4K"):
                if q.lower() in title.lower():
                    quality = q
                    break

            results.append(
                SearchResult(
                    id=f"nyaa:{link}",
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
        """Nyaa provides magnet/torrent links - extract from the link."""
        # item.id format: "nyaa:https://nyaa.si/view/12345"
        if ":" not in item.id:
            return []
        _, url = item.id.split(":", 1)

        # For now, return the page URL - user would need to open in browser
        # or we could parse the page for magnet link
        return [
            StreamLink(
                url=url,
                quality="torrent",
                is_live=False,
            )
        ]


class SubsPleaseSource(Source):
    """SubsPlease - latest anime releases (RSS feed)."""

    id = "subsplease"
    name = "SubsPlease (Latest Anime)"
    category = "anime"

    SUBSPLEASE_RSS = "https://subsplease.org/rss/?r=1080"

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip().lower()
        if not query:
            return []

        try:
            req = urllib.request.Request(
                self.SUBSPLEASE_RSS,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml"},
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SourceError(f"SubsPlease error: HTTP {code}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SourceError(f"Timeout: {exc}") from exc

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise SourceError(f"Bad RSS response: {exc}") from exc

        results = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_date_elem = item.find("pubDate")

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            pub_date = (pub_date_elem.text or "") if pub_date_elem is not None else ""

            # Filter by query
            if query not in title.lower():
                continue

            # Parse title format: "[SubsPlease] Title - EP (quality)"
            import re

            clean_title = re.sub(r"\[.*?\]\s*", "", title)
            ep_match = re.search(r"[-–]\s*(\d+)", clean_title)
            episode_num = ep_match.group(1) if ep_match else ""

            quality = "1080p"
            if "2160p" in title or "4K" in title:
                quality = "2160p"
            elif "720p" in title:
                quality = "720p"

            results.append(
                SearchResult(
                    id=f"subsplease:{link}",
                    title=f"{clean_title} Ep {episode_num}" if episode_num else clean_title,
                    kind=MediaKind.ANIME,
                    source_id=self.id,
                    year=None,
                    poster_url=None,
                    overview=f"Released: {pub_date} · {quality}",
                    genres=("anime", "simulcast"),
                )
            )
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """SubsPlease provides direct download links or magnet links."""
        if ":" not in item.id:
            return []
        _, url = item.id.split(":", 1)

        quality = "1080p"
        if "2160p" in item.title or "4K" in item.title:
            quality = "2160p"
        elif "720p" in item.title:
            quality = "720p"

        return [
            StreamLink(
                url=url,
                quality=quality,
                is_live=False,
            )
        ]
