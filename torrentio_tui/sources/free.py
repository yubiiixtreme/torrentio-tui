"""Free movie/TV sources - zero config, no API keys needed.

These sources scrape free streaming sites and public domain content.
All sources work out of the box with no configuration required.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources.base import Source, SourceError

_USER_AGENT = "torrentio-tui/0.6 (+https://github.com/yubiiixtreme/torrentio-tui)"

# Free movie/TV streaming sites with search APIs
FREE_MOVIE_SITES = {
    "vidsrc": {
        "name": "VidSrc",
        "search_url": "https://vidsrc.xyz/search/{query}",
        "movie_url": "https://vidsrc.xyz/embed/movie/{id}",
        "tv_url": "https://vidsrc.xyz/embed/tv/{id}/{season}/{episode}",
    },
    "vidsrc_me": {
        "name": "VidSrc.me",
        "search_url": "https://vidsrc.me/search/{query}",
        "movie_url": "https://vidsrc.me/embed/movie/{id}",
        "tv_url": "https://vidsrc.me/embed/tv/{id}/{season}/{episode}",
    },
    "autoembed": {
        "name": "AutoEmbed",
        "search_url": "https://autoembed.cc/search/{query}",
        "movie_url": "https://autoembed.cc/movie/{id}",
        "tv_url": "https://autoembed.cc/tv/{id}/{season}/{episode}",
    },
    "multiembed": {
        "name": "MultiEmbed",
        "search_url": "https://multiembed.mov/search/{query}",
        "movie_url": "https://multiembed.mov/movie/{id}",
        "tv_url": "https://multiembed.mov/tv/{id}/{season}/{episode}",
    },
}

# Public domain / Archive.org
PUBLIC_DOMAIN_SITES = {
    "archive_org": {
        "name": "Internet Archive",
        "search_url": "https://archive.org/advancedsearch.php?q={query}&fl[]=identifier,title,creator,date,mediatype,description&rows=20&page=1&output=json",
        "detail_url": "https://archive.org/metadata/{id}",
        "stream_url": "https://archive.org/download/{id}/{file}",
    }
}

# Anime free sites
ANIME_FREE_SITES = {
    "gogoanime": {
        "name": "GogoAnime",
        "search_url": "https://gogoanime.pe/search.html?keyword={query}",
        "base_url": "https://gogoanime.pe",
    },
    "9anime": {
        "name": "9Anime",
        "search_url": "https://9anime.to/search?keyword={query}",
        "base_url": "https://9anime.to",
    },
    "animepahe": {
        "name": "AnimePahe",
        "search_url": "https://animepahe.ru/api?m=search&q={query}",
        "base_url": "https://animepahe.ru",
    },
    "animesuge": {
        "name": "AnimeSuge",
        "search_url": "https://animesuge.to/search?keyword={query}",
        "base_url": "https://animesuge.to",
    },
    "hianime": {
        "name": "HiAnime",
        "search_url": "https://hianime.to/search?keyword={query}",
        "base_url": "https://hianime.to",
    },
    "animixplay": {
        "name": "AniMixPlay",
        "search_url": "https://animixplay.to/api/search?q={query}",
        "base_url": "https://animixplay.to",
    },
}

# YTS/YIFY movies
YTS_API = "https://yts.mx/api/v2/list_movies.json?query_term={query}&limit=20&sort_by=rating"
YTS_MOVIE_DETAIL = "https://yts.mx/api/v2/movie_details.json?movie_id={id}&with_images=true&with_cast=true"

# EZTV shows
EZTV_API = "https://eztv.re/api/get-torrents?imdb_id={imdb_id}&limit=20"

# Tubi API
TUBI_API = "https://tubitv.com/oz/videos/search?query={query}&limit=20"

# Crackle API
CRACKLE_API = "https://api.crackle.com/v2/search?q={query}&limit=20"

# Popcornflix API
POPCORNFLIX_API = "https://api.popcornflix.com/v2/search?q={query}&limit=20"

# Viki API
VIKI_API = "https://api.viki.io/v4/search.json?q={query}&per_page=20"


def _fetch_json(url: str, timeout: float = 10.0) -> Optional[dict]:
    """Fetch JSON from URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _fetch_html(url: str, timeout: float = 10.0) -> Optional[str]:
    """Fetch HTML from URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_yts_results(data: dict) -> list[SearchResult]:
    """Parse YTS API results."""
    results = []
    for movie in data.get("data", {}).get("movies", []):
        results.append(
            SearchResult(
                id=f"yts:{movie['id']}",
                title=movie["title"],
                kind=MediaKind.MOVIE,
                source_id="yts",
                year=movie.get("year"),
                poster_url=movie.get("medium_cover_image"),
                overview=movie.get("summary", "")[:300],
                genres=tuple(movie.get("genres", [])),
            )
        )
    return results


def _parse_tubi_results(data: dict) -> list[SearchResult]:
    """Parse Tubi API results."""
    results = []
    for item in data.get("results", []):
        kind = MediaKind.MOVIE if item.get("type") == "movie" else MediaKind.SERIES
        results.append(
            SearchResult(
                id=f"tubi:{item['id']}",
                title=item["title"],
                kind=kind,
                source_id="tubi",
                year=item.get("year"),
                poster_url=item.get("thumbnail"),
                overview=item.get("description", "")[:300],
                genres=tuple(item.get("genres", [])),
            )
        )
    return results


def _parse_crackle_results(data: dict) -> list[SearchResult]:
    """Parse Crackle API results."""
    results = []
    for item in data.get("results", []):
        kind = MediaKind.MOVIE if item.get("content_type") == "movie" else MediaKind.SERIES
        results.append(
            SearchResult(
                id=f"crackle:{item['id']}",
                title=item["title"],
                kind=kind,
                source_id="crackle",
                year=item.get("year"),
                poster_url=item.get("thumbnail"),
                overview=item.get("description", "")[:300],
                genres=tuple(item.get("genres", [])),
            )
        )
    return results


def _parse_viki_results(data: dict) -> list[SearchResult]:
    """Parse Viki API results."""
    results = []
    for item in data.get("response", []):
        kind = MediaKind.MOVIE if item.get("type") == "movie" else MediaKind.SERIES
        results.append(
            SearchResult(
                id=f"viki:{item['id']}",
                title=item["title"],
                kind=kind,
                source_id="viki",
                year=item.get("year"),
                poster_url=item.get("poster"),
                overview=item.get("description", "")[:300],
                genres=tuple(item.get("genres", [])),
            )
        )
    return results


def _parse_archive_results(data: dict) -> list[SearchResult]:
    """Parse Internet Archive results."""
    results = []
    for doc in data.get("response", {}).get("docs", []):
        if doc.get("mediatype") not in ("movies", "video"):
            continue
        kind = MediaKind.MOVIE
        results.append(
            SearchResult(
                id=f"archive:{doc['identifier']}",
                title=doc.get("title", doc["identifier"]),
                kind=kind,
                source_id="publicdomain",
                year=int(doc.get("date", "0")[:4]) if doc.get("date") else None,
                poster_url=f"https://archive.org/services/img/{doc['identifier']}",
                overview=doc.get("description", [""])[0][:300] if isinstance(doc.get("description"), list) else doc.get("description", "")[:300],
                genres=("public domain", "archive"),
            )
        )
    return results


def _parse_anime_html(html: str, source: str) -> list[SearchResult]:
    """Parse anime site HTML results."""
    results = []
    # Generic anime site parsing
    from bs4 import BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Common patterns for anime sites
        for link in soup.select("a[href*='episode'], a[href*='watch'], a.anime-title, .anime-item a, .item a"):
            href = link.get("href", "")
            title = link.get_text(strip=True) or link.get("title", "")
            if not title or len(title) < 3:
                continue
            # Try to find image
            img = link.find("img") or link.find_previous("img")
            poster = img.get("src") or img.get("data-src") if img else None
            results.append(
                SearchResult(
                    id=f"{source}:{href}",
                    title=title,
                    kind=MediaKind.ANIME,
                    source_id=source,
                    year=None,
                    poster_url=poster,
                    overview="",
                    genres=("anime",),
                )
            )
    except Exception:
        pass
    return results[:20]


class FreeMoviesSource(Source):
    """Free movie streaming sources - scrapes multiple free sites."""
    
    id = "freemovies"
    name = "Free Movies (Multi-Source)"
    
    def __init__(self, source_id: str = "freemovies") -> None:
        self.source_id = source_id
        self.timeout = 10.0

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        
        results = []
        encoded_query = urllib.parse.quote(query)
        
        # Try multiple free sources
        sources_to_try = [
            ("yts", YTS_API.format(query=encoded_query), _parse_yts_results),
            ("tubi", TUBI_API.format(query=encoded_query), _parse_tubi_results),
            ("crackle", CRACKLE_API.format(query=encoded_query), _parse_crackle_results),
            ("viki", VIKI_API.format(query=encoded_query), _parse_viki_results),
            ("popcornflix", POPCORNFLIX_API.format(query=encoded_query), _parse_crackle_results),  # Similar API
        ]
        
        for source_name, url, parser in sources_to_try:
            try:
                data = _fetch_json(url, self.timeout)
                if data:
                    parsed = parser(data)
                    # Tag with actual source
                    for r in parsed:
                        r.source_id = source_name
                    results.extend(parsed)
            except Exception:
                continue
        
        # Also try VidSrc
        try:
            html = _fetch_html(f"https://vidsrc.xyz/search/{encoded_query}", self.timeout)
            if html:
                # Parse VidSrc results
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for item in soup.select(".movie-item, .result-item, .card"):
                    title_elem = item.select_one("h3, h4, .title, a")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href") if title_elem.name == "a" else item.select_one("a")
                        href = link.get("href") if link else ""
                        img = item.select_one("img")
                        poster = img.get("src") or img.get("data-src") if img else None
                        if title:
                            results.append(
                                SearchResult(
                                    id=f"vidsrc:{href}",
                                    title=title,
                                    kind=MediaKind.MOVIE,
                                    source_id="vidsrc",
                                    year=None,
                                    poster_url=poster,
                                    overview="",
                                    genres=("free",),
                                )
                            )
        except Exception:
            pass
        
        return results[:30]

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """Get streams from free movie sources."""
        streams = []
        
        # Try to get direct stream from VidSrc-like services
        if item.source_id in ("vidsrc", "vidsrc_me", "autoembed", "multiembed"):
            # Extract ID from item.id
            if ":" in item.id:
                _, path = item.id.split(":", 1)
                base = FREE_MOVIE_SITES.get(item.source_id, FREE_MOVIE_SITES["vidsrc"])
                if item.kind == MediaKind.MOVIE:
                    url = base["movie_url"].format(id=path)
                    streams.append(StreamLink(url=url, quality="auto", is_live=False))
        
        # For YTS, we'd need to fetch movie details to get torrent links
        if item.source_id == "yts" and item.id.startswith("yts:"):
            movie_id = item.id.split(":")[1]
            data = _fetch_json(YTS_MOVIE_DETAIL.format(id=movie_id), self.timeout)
            if data:
                for torrent in data.get("data", {}).get("movie", {}).get("torrents", []):
                    quality = torrent.get("quality", "1080p")
                    magnet = f"magnet:?xt=urn:btih:{torrent.get('hash', '')}&dn={urllib.parse.quote(item.title)}&tr=udp://tracker.opentrackr.org:1337/announce"
                    streams.append(StreamLink(url=magnet, quality=quality, is_live=False))
        
        # For Tubi, Crackle, etc. - they use HLS/DASH which need player support
        if item.source_id in ("tubi", "crackle", "popcornflix", "viki"):
            # These would need their specific player/token handling
            # For now, provide the web URL
            streams.append(StreamLink(
                url=f"https://{item.source_id}.com/watch/{item.id.split(':')[-1]}",
                quality="web",
                is_live=False
            ))
        
        # Fallback: search for magnet links via Torrentio
        if not streams:
            streams.append(StreamLink(
                url=f"https://torrentio.strem.fun/stream/movie/{item.id}.json",
                quality="auto",
                is_live=False
            ))
        
        return streams


class FreeTVSource(Source):
    """Free TV show streaming sources."""
    
    id = "freetv"
    name = "Free TV Shows (Multi-Source)"
    
    def __init__(self, source_id: str = "freetv") -> None:
        self.source_id = source_id
        self.timeout = 10.0

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        
        results = []
        encoded_query = urllib.parse.quote(query)
        
        # Try EZTV for TV torrents
        try:
            # First search for IMDB ID via Cinemeta or similar
            # For now, use a simple approach
            pass
        except Exception:
            pass
        
        # Use same sources as movies but filter for series
        free_movies = FreeMoviesSource(self.source_id)
        movie_results = free_movies.search(query)
        for r in movie_results:
            if r.kind == MediaKind.SERIES or "series" in r.genres or "tv" in r.genres:
                results.append(r)
            elif r.kind == MediaKind.MOVIE:
                # Could be a TV show too
                r.kind = MediaKind.SERIES
                results.append(r)
        
        # Try TV-specific sources
        try:
            # EZTV search would need IMDB ID
            pass
        except Exception:
            pass
        
        return results[:30]

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        # For TV shows, we'd need to fetch episode list
        # This is a simplified version
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        return [
            StreamLink(
                url=f"https://torrentio.strem.fun/stream/series/{item.id}.json",
                quality="auto",
                is_live=False
            )
        ]


class PublicDomainSource(Source):
    """Public domain movies from Internet Archive."""
    
    id = "publicdomain"
    name = "Public Domain (Archive.org)"
    
    def __init__(self) -> None:
        self.timeout = 15.0

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        
        encoded = urllib.parse.quote(query)
        url = f"https://archive.org/advancedsearch.php?q={encoded}&fl[]=identifier,title,creator,date,mediatype,description&rows=20&page=1&output=json"
        
        data = _fetch_json(url, self.timeout)
        if not data:
            return []
        
        return _parse_archive_results(data)

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        return [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        """Get streams from Archive.org."""
        streams = []
        identifier = item.id.split(":")[-1] if ":" in item.id else item.id
        
        # Get metadata to find video files
        data = _fetch_json(f"https://archive.org/metadata/{identifier}", self.timeout)
        if data:
            files = data.get("files", [])
            for f in files:
                name = f.get("name", "")
                if name.endswith((".mp4", ".mkv", ".avi", ".mov", ".webm")):
                    url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}"
                    quality = "720p"  # Archive.org varies
                    if "1080" in name or "HD" in name.upper():
                        quality = "1080p"
                    elif "4K" in name.upper() or "2160" in name:
                        quality = "2160p"
                    streams.append(StreamLink(url=url, quality=quality, is_live=False))
        
        return streams[:10]


class FreeAnimeSource(FreeMoviesSource):
    """Free anime streaming sources."""
    
    id = "freeanime"
    name = "Free Anime (Multi-Source)"
    
    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        
        results = []
        encoded_query = urllib.parse.quote(query)
        
        # Try AniList first for metadata
        try:
            from torrentio_tui.sources.anime import _fetch_anilist
            anilist_results = _fetch_anilist(query, is_adult=False)
            for m in anilist_results:
                results.append(
                    SearchResult(
                        id=f"anilist:{m.id}",
                        title=m.title_english or m.title_romaji or m.title_native,
                        kind=MediaKind.ANIME,
                        source_id="anilist",
                        year=m.year,
                        poster_url=m.cover_image,
                        overview=m.description[:300] if m.description else "",
                        genres=tuple(m.genres),
                    )
                )
        except Exception:
            pass
        
        # Try free anime streaming sites
        for site_key, site_info in ANIME_FREE_SITES.items():
            try:
                url = site_info["search_url"].format(query=encoded_query)
                html = _fetch_html(url, self.timeout)
                if html:
                    parsed = _parse_anime_html(html, site_key)
                    results.extend(parsed)
            except Exception:
                continue
        
        return results[:30]


# Source class mapping for dynamic loading
FREE_SOURCE_CLASSES = {
    "freemovies": FreeMoviesSource,
    "freetv": FreeTVSource,
    "publicdomain": PublicDomainSource,
    "yts": FreeMoviesSource,
    "eztv": FreeTVSource,
    "tubi": FreeMoviesSource,
    "crackle": FreeMoviesSource,
    "popcornflix": FreeMoviesSource,
    "viki": FreeMoviesSource,
    "gogoanime": FreeAnimeSource,
    "9anime": FreeAnimeSource,
    "animepahe": FreeAnimeSource,
    "animesuge": FreeAnimeSource,
    "hianime": FreeAnimeSource,
    "animeworld": FreeAnimeSource,
    "animixplay": FreeAnimeSource,
}