"""Metadata catalogue sources: TVMaze, Jikan (MyAnimeList), Kitsu,
MangaDex, iTunes, TMDB, Trakt.

These are *discovery* companions, not stream indexes — the keyless APIs
are free, and each is stronger than Cinemeta somewhere (TVMaze for
series air-dates/episodes, Jikan/Kitsu for anime depth, MangaDex for
manga with cover art, iTunes for movies/TV with poster art). To avoid
the classic dead-end catalogue (results that can never play), every
source here bridges to playable streams through a Stremio-protocol
stream addon — TVMaze via the show's IMDb external id when available,
otherwise (and for the rest) via a Cinemeta title resolve — so the
user's configured addon (debrid URL included) does the streaming.
"""

from __future__ import annotations

import contextlib
import html
import re
import time
import urllib.error
import urllib.parse

from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, open_url
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.sources.stremio import StremioSource

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(text: str | None, limit: int = 300) -> str:
    if not text:
        return ""
    plain = html.unescape(_TAG_RE.sub("", text)).strip()
    return plain[:limit] if len(plain) > limit else plain


def _get_json(
    url: str,
    timeout: float,
    proxy_url: str | None,
    accept: str = "application/json",
):
    headers = {"User-Agent": _USER_AGENT, "Accept": accept}
    last_exc: Exception | None = None
    for attempt in range(2):  # one retry on transient 5xx
        try:
            import json

            with open_url(url, timeout, proxy_url, headers) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 404:
                return None
            if code not in (500, 502, 503, 504) or attempt == 1:
                raise SourceError(f"Request failed (HTTP {code}): {url}") from exc
            last_exc = exc
            time.sleep(1.0)
        except urllib.error.URLError as exc:
            raise SourceError(f"Network error for {url}: {exc.reason}") from exc
        except (ValueError, TimeoutError) as exc:
            raise SourceError(f"Bad response from {url}: {exc}") from exc
    raise SourceError(f"Request failed after retry: {url}") from last_exc


def _parse_year(text: str | int | None) -> int | None:
    if isinstance(text, int):
        return text if 1900 <= text <= 2100 else None
    if isinstance(text, str) and len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        return year if 1900 <= year <= 2100 else None
    return None


class BridgedCatalogueSource(Source):
    """Base for metadata sources that resolve playback through a
    Stremio-protocol stream addon (`self._streams`)."""

    category = "catalogue"
    supports_live = False
    #: Overridden by APIs that require a vendor content type (Kitsu/JSON:API).
    api_accept = "application/json"

    def __init__(
        self,
        stream_url: str | None = None,
        cinemeta_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        source_id: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.proxy_url = proxy_url
        if source_id:
            self.id = source_id
        # Never surfaces in the UI (results carry this source's id); it
        # just borrows the user's configured stream addon for playback.
        # Env overrides (TORRENTIO_TUI_STREAM_URL, ...) apply inside, so a
        # debrid URL configured for `stremio` benefits these sources too.
        self._streams = StremioSource(
            cinemeta_url=cinemeta_url,
            stream_url=stream_url,
            timeout=timeout,
            proxy_url=proxy_url,
            source_id=f"{self.id}-bridge",
        )

    # -- bridging -------------------------------------------------------
    def _series_streams_by_imdb(
        self, imdb_id: str, title: str, season: int | None, number: int | None
    ) -> list[StreamLink]:
        """Direct bridge: IMDb id + S/E → `/stream/series/tt..:S:E.json`."""
        item = SearchResult(
            id=f"series:{imdb_id}", title=title, kind=MediaKind.SERIES, source_id=self.id
        )
        if season is None or number is None:
            episode = Episode(id=imdb_id, title=title)
        else:
            episode = Episode(
                id=f"{imdb_id}:{season}:{number}",
                title=f"S{season:02d}E{number:02d}",
                season=season,
                number=number,
            )
        links = self._streams.get_streams(item, episode)
        if not links:
            raise SourceError(f"No streams found for {title!r} via the stream addon")
        return links

    def _bridge_by_title(
        self,
        title: str,
        kind: MediaKind,
        season: int | None = None,
        number: int | None = None,
    ) -> list[StreamLink]:
        """Fallback bridge: Cinemeta title search, then episode-number
        match. Best effort for multi-season anime with absolute numbering."""
        try:
            matches = self._streams.search(title)
        except SourceError as exc:
            raise SourceError(f"Could not resolve {title!r} for playback: {exc}") from exc
        wanted = {kind} | (
            {MediaKind.SERIES, MediaKind.MOVIE} if kind == MediaKind.ANIME else set()
        )
        candidates = [m for m in matches if m.kind in wanted] or matches
        if not candidates:
            raise SourceError(
                f"{title!r} is metadata-only here — no playable match. "
                "Search the same title under a stream source (stremio, comet, ...)."
            )
        picked = candidates[0]
        if picked.kind == MediaKind.MOVIE or (season is None and number is None):
            links = self._streams.get_streams(picked, Episode(id=picked.id, title=picked.title))
        else:
            episodes = self._streams.get_episodes(picked)
            ep = next(
                (
                    e
                    for e in episodes
                    if (season is None or e.season in (None, season))
                    and (number is None or e.number == number)
                ),
                None,
            )
            if ep is None:
                raise SourceError(
                    f"Found {picked.title!r} but not episode "
                    f"{f'S{season}E{number}' if season else f'#{number}'}."
                )
            links = self._streams.get_streams(picked, ep)
        if not links:
            raise SourceError(f"No streams found for {title!r} via the stream addon")
        return links


class TVMazeSource(BridgedCatalogueSource):
    """TVMaze — series catalogue (air-dates, episode lists) with IMDb-id
    stream bridging. Free, no key."""

    id = "tvmaze"
    name = "TVMaze (Series Catalogue)"

    API = "https://api.tvmaze.com"

    def __init__(self, api_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_url = (api_url or self.API).rstrip("/")
        self._shows: dict[int, dict] = {}

    def _show(self, show_id: int) -> dict:
        if show_id not in self._shows:
            data = _get_json(
                f"{self.api_url}/shows/{show_id}",
                self.timeout,
                self.proxy_url,
                self.api_accept,
            )
            if not isinstance(data, dict):
                raise SourceError(f"TVMaze has no show {show_id}")
            self._shows[show_id] = data
        return self._shows[show_id]

    @staticmethod
    def _to_result(show: dict, source_id: str) -> SearchResult | None:
        if not isinstance(show, dict) or not show.get("id"):
            return None
        genres = tuple(str(g) for g in show.get("genres") or [])
        kind = MediaKind.ANIME if "Anime" in genres else MediaKind.SERIES
        image = show.get("image") or {}
        rating = (show.get("rating") or {}).get("average")
        overview = _clean_html(show.get("summary"))
        if rating:
            overview = f"⭐ {rating}/10 — {overview}" if overview else f"⭐ {rating}/10"
        return SearchResult(
            id=f"tvmaze:{show['id']}",
            title=str(show.get("name", f"Show {show['id']}")),
            kind=kind,
            source_id=source_id,
            year=_parse_year(show.get("premiered")),
            poster_url=image.get("medium") or image.get("original"),
            overview=overview,
            genres=genres,
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        data = _get_json(
            f"{self.api_url}/search/shows?q={urllib.parse.quote(query)}",
            self.timeout,
            self.proxy_url,
            self.api_accept,
        )
        if not isinstance(data, list):
            return []
        results = []
        for row in data:
            if not isinstance(row, dict):
                continue
            show = row.get("show") or {}
            if isinstance(show, dict) and show.get("id"):
                self._shows[int(show["id"])] = show
                result = self._to_result(show, self.id)
                if result is not None:
                    results.append(result)
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        try:
            show_id = int(item.id.split(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SourceError(f"Bad TVMaze id: {item.id}") from exc
        data = _get_json(f"{self.api_url}/shows/{show_id}/episodes", self.timeout, self.proxy_url)
        if not isinstance(data, list):
            return [Episode(id=item.id, title=item.title)]
        episodes = []
        for ep in data:
            if not isinstance(ep, dict):
                continue
            season = ep.get("season") if isinstance(ep.get("season"), int) else None
            number = ep.get("number") if isinstance(ep.get("number"), int) else None
            name = ep.get("name") or f"Episode {number}"
            label = name
            if season is not None and number is not None:
                label = f"S{season:02d}E{number:02d} — {name}"
            episodes.append(
                Episode(
                    id=f"tvmaze:{show_id}:{ep.get('id', '')}",
                    title=label,
                    season=season,
                    number=number,
                )
            )
        episodes.sort(key=lambda e: (e.season or 0, e.number or 0))
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            show_id = int(item.id.split(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SourceError(f"Bad TVMaze id: {item.id}") from exc
        imdb_id = (self._show(show_id).get("externals") or {}).get("imdb_id")
        if imdb_id:
            try:
                return self._series_streams_by_imdb(
                    str(imdb_id), item.title, episode.season, episode.number
                )
            except SourceError:
                pass  # fall through to the title resolve below
        return self._bridge_by_title(
            item.title,
            MediaKind.SERIES,
            season=episode.season,
            number=episode.number,
        )


class JikanSource(BridgedCatalogueSource):
    """Jikan — MyAnimeList-backed anime catalogue (deep metadata, no key).
    Playback resolves through the stream addon by title."""

    id = "jikan"
    name = "Jikan (MyAnimeList Catalogue)"

    API = "https://api.jikan.moe/v4"

    def __init__(self, api_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_url = (api_url or self.API).rstrip("/")
        self._last_call_at: float = 0.0

    def _throttle(self) -> None:
        # Jikan allows 3 req/s — stay comfortably under it.
        wait = 0.4 - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        self._last_call_at = time.monotonic()

    def _api(self, path: str) -> dict | list | None:
        self._throttle()
        return _get_json(f"{self.api_url}{path}", self.timeout, self.proxy_url, self.api_accept)

    @staticmethod
    def _to_result(anime: dict, source_id: str) -> SearchResult | None:
        if not isinstance(anime, dict) or anime.get("mal_id") is None:
            return None
        images = (anime.get("images") or {}).get("jpg") or {}
        aired = (anime.get("aired") or {}).get("prop", {}).get("from", {})
        year = aired.get("year") if isinstance(aired, dict) else None
        kind = MediaKind.MOVIE if anime.get("type") == "Movie" else MediaKind.ANIME
        genres = tuple(g.get("name", "") for g in anime.get("genres") or [] if isinstance(g, dict))
        score = anime.get("score")
        overview = (anime.get("synopsis") or "")[:300]
        if score:
            overview = f"⭐ {score}/10 — {overview}" if overview else f"⭐ {score}/10"
        return SearchResult(
            id=f"jikan:{anime['mal_id']}",
            title=str(anime.get("title_english") or anime.get("title")),
            kind=kind,
            source_id=source_id,
            year=year if isinstance(year, int) else None,
            poster_url=images.get("large_image_url") or images.get("image_url"),
            overview=overview,
            genres=genres,
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        data = self._api(
            f"/anime?q={urllib.parse.quote(query)}&limit=15&order_by=members&sort=desc"
        )
        if not isinstance(data, dict):
            return []
        results = []
        for anime in data.get("data") or []:
            result = self._to_result(anime, self.id)
            if result is not None:
                results.append(result)
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        try:
            mal_id = int(item.id.split(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SourceError(f"Bad Jikan id: {item.id}") from exc
        if item.kind == MediaKind.MOVIE:
            return [Episode(id=item.id, title=item.title)]
        episodes: list[Episode] = []
        page = 1
        while page <= 5:  # cap: ~500 episodes, past any sane season
            data = self._api(f"/anime/{mal_id}/episodes?page={page}")
            if not isinstance(data, dict):
                break
            for ep in data.get("data") or []:
                if not isinstance(ep, dict) or ep.get("episode") is None:
                    continue
                try:
                    number = int(ep["episode"])
                except (ValueError, TypeError):
                    continue
                episodes.append(
                    Episode(
                        id=f"jikan:{mal_id}:{number}",
                        title=ep.get("title") or f"Episode {number}",
                        season=1,
                        number=number,
                    )
                )
            pagination = data.get("pagination") or {}
            if not pagination.get("has_next_page"):
                break
            page += 1
        episodes.sort(key=lambda e: e.number or 0)
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        if item.kind == MediaKind.MOVIE:
            return self._bridge_by_title(item.title, MediaKind.MOVIE)
        return self._bridge_by_title(item.title, MediaKind.ANIME, number=episode.number)


class KitsuSource(BridgedCatalogueSource):
    """Kitsu — anime/manga catalogue with trending data (JSON:API, no key).
    Playback resolves through the stream addon by title."""

    id = "kitsu"
    name = "Kitsu (Anime Catalogue)"

    api_accept = "application/vnd.api+json"

    API = "https://kitsu.io/api/edge"

    def __init__(self, api_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_url = (api_url or self.API).rstrip("/")

    @staticmethod
    def _to_result(entry: dict, source_id: str) -> SearchResult | None:
        if not isinstance(entry, dict) or not entry.get("id"):
            return None
        attrs = entry.get("attributes") or {}
        titles = attrs.get("titles") or {}
        poster = attrs.get("posterImage") or {}
        kind = MediaKind.MOVIE if attrs.get("showType") == "movie" else MediaKind.ANIME
        rating = attrs.get("averageRating")
        overview = (attrs.get("synopsis") or "")[:300]
        if rating:
            with contextlib.suppress(ValueError, TypeError):
                overview = f"⭐ {float(rating) / 10:.1f}/10 — {overview}"
        return SearchResult(
            id=f"kitsu:{entry['id']}",
            title=str(
                attrs.get("canonicalTitle")
                or titles.get("en")
                or titles.get("en_us")
                or entry["id"]
            ),
            kind=kind,
            source_id=source_id,
            year=_parse_year(attrs.get("startDate")),
            poster_url=poster.get("medium") or poster.get("original"),
            overview=overview,
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        data = _get_json(
            f"{self.api_url}/anime?filter[text]={urllib.parse.quote(query)}&page[limit]=10",
            self.timeout,
            self.proxy_url,
            self.api_accept,
        )
        if not isinstance(data, dict):
            return []
        results = []
        for entry in data.get("data") or []:
            result = self._to_result(entry, self.id)
            if result is not None:
                results.append(result)
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        try:
            kitsu_id = item.id.split(":", 1)[1]
        except IndexError as exc:
            raise SourceError(f"Bad Kitsu id: {item.id}") from exc
        if item.kind == MediaKind.MOVIE:
            return [Episode(id=item.id, title=item.title)]
        episodes: list[Episode] = []
        offset = 0
        while offset < 500:  # cap: past any sane episode count
            data = _get_json(
                f"{self.api_url}/anime/{kitsu_id}/episodes"
                f"?page[limit]=20&page[offset]={offset}&sort=number",
                self.timeout,
                self.proxy_url,
                self.api_accept,
            )
            rows = data.get("data") if isinstance(data, dict) else None
            if not rows:
                break
            for row in rows:
                attrs = row.get("attributes") or {} if isinstance(row, dict) else {}
                number = attrs.get("number")
                if not isinstance(number, int):
                    continue
                episodes.append(
                    Episode(
                        id=f"kitsu:{kitsu_id}:{number}",
                        title=str(attrs.get("canonicalTitle") or f"Episode {number}"),
                        season=1,
                        number=number,
                    )
                )
            offset += 20
        episodes.sort(key=lambda e: e.number or 0)
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        if item.kind == MediaKind.MOVIE:
            return self._bridge_by_title(item.title, MediaKind.MOVIE)
        return self._bridge_by_title(item.title, MediaKind.ANIME, number=episode.number)


class TMDBSource(BridgedCatalogueSource):
    """TMDB (The Movie Database) — comprehensive movie/TV catalogue with
    API key. Free tier available at https://www.themoviedb.org/settings/api."""

    id = "tmdb"
    name = "TMDB (Movie/TV Catalogue)"

    API = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

    def __init__(
        self,
        api_key: str | None = None,
        stream_url: str | None = None,
        cinemeta_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        source_id: str | None = None,
    ) -> None:
        super().__init__(
            stream_url=stream_url,
            cinemeta_url=cinemeta_url,
            timeout=timeout,
            proxy_url=proxy_url,
            source_id=source_id,
        )
        import os

        self.api_key = api_key or os.environ.get("TMDB_API_KEY", "")

    def _api(self, path: str, params: dict | None = None) -> dict | list | None:
        if not self.api_key:
            raise SourceError("TMDB API key required. Set TMDB_API_KEY env var or add to config.")
        params = params or {}
        params["api_key"] = self.api_key
        query = urllib.parse.urlencode(params)
        url = f"{self.API}{path}?{query}"
        return _get_json(url, self.timeout, self.proxy_url)

    def _to_movie_result(self, movie: dict, source_id: str) -> SearchResult | None:
        if not isinstance(movie, dict) or not movie.get("id"):
            return None
        poster = movie.get("poster_path")
        poster_url = f"{self.IMAGE_BASE}{poster}" if poster else None
        genres = tuple(g.get("name", "") for g in movie.get("genres", []) if isinstance(g, dict))
        year = _parse_year(movie.get("release_date"))
        overview = movie.get("overview") or ""
        vote = movie.get("vote_average")
        if vote:
            overview = f"⭐ {vote}/10 — {overview}" if overview else f"⭐ {vote}/10"
        return SearchResult(
            id=f"tmdb:movie:{movie['id']}",
            title=str(movie.get("title", f"Movie {movie['id']}")),
            kind=MediaKind.MOVIE,
            source_id=source_id,
            year=year,
            poster_url=poster_url,
            overview=overview[:300],
            genres=genres,
        )

    def _to_tv_result(self, show: dict, source_id: str) -> SearchResult | None:
        if not isinstance(show, dict) or not show.get("id"):
            return None
        poster = show.get("poster_path")
        poster_url = f"{self.IMAGE_BASE}{poster}" if poster else None
        genres = tuple(g.get("name", "") for g in show.get("genres", []) if isinstance(g, dict))
        kind = MediaKind.ANIME if "Animation" in genres or "Anime" in genres else MediaKind.SERIES
        year = _parse_year(show.get("first_air_date"))
        overview = show.get("overview") or ""
        vote = show.get("vote_average")
        if vote:
            overview = f"⭐ {vote}/10 — {overview}" if overview else f"⭐ {vote}/10"
        return SearchResult(
            id=f"tmdb:tv:{show['id']}",
            title=str(show.get("name", f"Show {show['id']}")),
            kind=kind,
            source_id=source_id,
            year=year,
            poster_url=poster_url,
            overview=overview[:300],
            genres=genres,
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results = []
        data = self._api("/search/movie", {"query": query, "page": 1})
        if isinstance(data, dict):
            for movie in data.get("results", [])[:10]:
                res = self._to_movie_result(movie, self.id)
                if res:
                    results.append(res)
        data = self._api("/search/tv", {"query": query, "page": 1})
        if isinstance(data, dict):
            for show in data.get("results", [])[:10]:
                res = self._to_tv_result(show, self.id)
                if res:
                    results.append(res)
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        try:
            _, media_type, tmdb_id = item.id.split(":", 2)
        except ValueError as exc:
            raise SourceError(f"Bad TMDB id: {item.id}") from exc

        if media_type == "movie":
            return [Episode(id=item.id, title=item.title)]

        data = self._api(f"/tv/{tmdb_id}", {"append_to_response": "external_ids"})
        if not isinstance(data, dict):
            return [Episode(id=item.id, title=item.title)]

        episodes = []
        for season in data.get("seasons", []):
            season_num = season.get("season_number")
            if season_num == 0:
                continue
            ep_data = self._api(f"/tv/{tmdb_id}/season/{season_num}")
            if not isinstance(ep_data, dict):
                continue
            for ep in ep_data.get("episodes", []):
                ep_num = ep.get("episode_number")
                if not isinstance(ep_num, int):
                    continue
                episodes.append(
                    Episode(
                        id=f"tmdb:tv:{tmdb_id}:{season_num}:{ep_num}",
                        title=ep.get("name") or f"Episode {ep_num}",
                        season=season_num,
                        number=ep_num,
                    )
                )
        episodes.sort(key=lambda e: (e.season or 0, e.number or 0))
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            parts = item.id.split(":")
            if len(parts) >= 3:
                media_type = parts[1]
                tmdb_id = parts[2]
                ext_data = self._api(f"/{media_type}/{tmdb_id}/external_ids")
                if isinstance(ext_data, dict) and ext_data.get("imdb_id"):
                    imdb_id = ext_data["imdb_id"]
                    if media_type == "tv":
                        return self._series_streams_by_imdb(
                            imdb_id, item.title, episode.season, episode.number
                        )
                    return self._bridge_by_title(item.title, MediaKind.MOVIE)
        except Exception:
            pass
        kind = item.kind
        if kind == MediaKind.ANIME:
            kind = MediaKind.SERIES
        return self._bridge_by_title(item.title, kind, season=episode.season, number=episode.number)


class TraktSource(BridgedCatalogueSource):
    """Trakt.tv — personal media tracking with trending/popular lists.
    Needs API key from https://trakt.tv/oauth/applications."""

    id = "trakt"
    name = "Trakt (Trending/Personal)"

    API = "https://api.trakt.tv"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        stream_url: str | None = None,
        cinemeta_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        source_id: str | None = None,
    ) -> None:
        super().__init__(
            stream_url=stream_url,
            cinemeta_url=cinemeta_url,
            timeout=timeout,
            proxy_url=proxy_url,
            source_id=source_id,
        )
        import os

        self.client_id = client_id or os.environ.get("TRAKT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("TRAKT_CLIENT_SECRET", "")

    def _headers(self) -> dict:
        return {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
        }

    def _trakt_get(self, path: str, params: dict | None = None) -> dict | list | None:
        if not self.client_id:
            raise SourceError(
                "Trakt client ID required. Set TRAKT_CLIENT_ID env var or add to config."
            )
        query = urllib.parse.urlencode(params or {})
        url = f"{self.API}{path}?{query}"
        headers = self._headers()
        try:
            with open_url(url, self.timeout, self.proxy_url, headers) as resp:
                import json

                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 404:
                return None
            raise SourceError(f"Trakt request failed (HTTP {code}): {url}") from exc
        except Exception as exc:
            raise SourceError(f"Trakt error: {exc}") from exc

    def _to_movie_result(self, item: dict, source_id: str) -> SearchResult | None:
        movie = item.get("movie") if "movie" in item else item
        if not isinstance(movie, dict) or not movie.get("ids"):
            return None
        tmdb_id = movie.get("ids", {}).get("tmdb")
        imdb_id = movie.get("ids", {}).get("imdb")
        year = movie.get("year")
        title = movie.get("title", "")
        overview = movie.get("overview", "")[:300]
        rating = movie.get("rating")
        if rating:
            overview = f"⭐ {rating}/10 — {overview}" if overview else f"⭐ {rating}/10"
        genres = tuple(movie.get("genres", []) or [])
        poster = None
        if tmdb_id:
            poster = f"https://image.tmdb.org/t/p/w500/{tmdb_id}"
        return SearchResult(
            id=f"trakt:movie:{movie['ids'].get('trakt', tmdb_id or imdb_id)}",
            title=title,
            kind=MediaKind.MOVIE,
            source_id=source_id,
            year=year,
            poster_url=poster,
            overview=overview,
            genres=genres,
        )

    def _to_show_result(self, item: dict, source_id: str) -> SearchResult | None:
        show = item.get("show") if "show" in item else item
        if not isinstance(show, dict) or not show.get("ids"):
            return None
        tmdb_id = show.get("ids", {}).get("tmdb")
        imdb_id = show.get("ids", {}).get("imdb")
        year = show.get("year")
        title = show.get("title", "")
        overview = show.get("overview", "")[:300]
        rating = show.get("rating")
        if rating:
            overview = f"⭐ {rating}/10 — {overview}" if overview else f"⭐ {rating}/10"
        genres = tuple(show.get("genres", []) or [])
        kind = MediaKind.ANIME if "anime" in genres or "animation" in genres else MediaKind.SERIES
        poster = None
        if tmdb_id:
            poster = f"https://image.tmdb.org/t/p/w500/{tmdb_id}"
        return SearchResult(
            id=f"trakt:show:{show['ids'].get('trakt', tmdb_id or imdb_id)}",
            title=title,
            kind=kind,
            source_id=source_id,
            year=year,
            poster_url=poster,
            overview=overview,
            genres=genres,
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        results = []
        data = self._trakt_get("/search/movie", {"query": query, "limit": 10})
        if isinstance(data, list):
            for item in data:
                res = self._to_movie_result(item, self.id)
                if res:
                    results.append(res)
        data = self._trakt_get("/search/show", {"query": query, "limit": 10})
        if isinstance(data, list):
            for item in data:
                res = self._to_show_result(item, self.id)
                if res:
                    results.append(res)
        return results

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        try:
            _, media_type, trakt_id = item.id.split(":", 2)
        except ValueError as exc:
            raise SourceError(f"Bad Trakt id: {item.id}") from exc

        if media_type == "movie":
            return [Episode(id=item.id, title=item.title)]

        data = self._trakt_get(f"/shows/{trakt_id}/seasons", {"extended": "episodes"})
        if not isinstance(data, list):
            return [Episode(id=item.id, title=item.title)]

        episodes = []
        for season in data:
            season_num = season.get("number")
            if season_num == 0:
                continue
            for ep in season.get("episodes", []):
                ep_num = ep.get("number")
                if not isinstance(ep_num, int):
                    continue
                episodes.append(
                    Episode(
                        id=f"trakt:show:{trakt_id}:{season_num}:{ep_num}",
                        title=ep.get("title") or f"Episode {ep_num}",
                        season=season_num,
                        number=ep_num,
                    )
                )
        episodes.sort(key=lambda e: (e.season or 0, e.number or 0))
        return episodes or [Episode(id=item.id, title=item.title)]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        try:
            parts = item.id.split(":")
            if len(parts) >= 3:
                media_type = parts[1]
                trakt_id = parts[2]
                ext_data = self._trakt_get(f"/{media_type}s/{trakt_id}", {"extended": "ids"})
                if isinstance(ext_data, dict):
                    imdb_id = ext_data.get("ids", {}).get("imdb")
                    if imdb_id:
                        if media_type == "show":
                            return self._series_streams_by_imdb(
                                imdb_id, item.title, episode.season, episode.number
                            )
                        return self._bridge_by_title(item.title, MediaKind.MOVIE)
        except Exception:
            pass
        kind = item.kind
        if kind == MediaKind.ANIME:
            kind = MediaKind.SERIES
        return self._bridge_by_title(item.title, kind, season=episode.season, number=episode.number)


class MangaDexSource(BridgedCatalogueSource):
    """MangaDex — manga/manhwa catalogue with real cover art (free,
    keyless). Playback of anime adaptations resolves through the stream
    addon by title, like the other catalogue companions."""

    id = "mangadex"
    name = "MangaDex (Manga Catalogue)"

    API = "https://api.mangadex.org"
    COVERS = "https://uploads.mangadex.org/covers"
    #: Keep the general catalogue clean — explicit adult manga lives
    #: behind the opt-in adult sources instead.
    RATINGS = ("safe", "suggestive", "erotica")

    def __init__(
        self,
        api_url: str | None = None,
        stream_url: str | None = None,
        cinemeta_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        source_id: str | None = None,
    ) -> None:
        super().__init__(
            stream_url=stream_url,
            cinemeta_url=cinemeta_url,
            timeout=timeout,
            proxy_url=proxy_url,
            source_id=source_id,
        )
        self.api_url = (api_url or self.API).rstrip("/")

    @staticmethod
    def _local_text(loc: object, preferred: tuple[str, ...] = ("en",)) -> str:
        if not isinstance(loc, dict):
            return ""
        for lang in preferred:
            value = loc.get(lang)
            if isinstance(value, str) and value:
                return value
        for value in loc.values():
            if isinstance(value, str) and value:
                return value
        return ""

    def _to_result(self, entry: dict) -> SearchResult | None:
        if not isinstance(entry, dict) or not entry.get("id"):
            return None
        manga_id = str(entry["id"])
        attrs = entry.get("attributes") or {}
        if not isinstance(attrs, dict):
            return None
        title = self._local_text(attrs.get("title"))
        if not title:
            for alt in attrs.get("altTitles") or []:
                title = self._local_text(alt)
                if title:
                    break
        if not title:
            return None
        overview = self._local_text(attrs.get("description"))[:300]
        tags = []
        for tag in attrs.get("tags") or []:
            name = (tag.get("attributes") or {}).get("name") if isinstance(tag, dict) else None
            label = self._local_text(name)
            if label:
                tags.append(label)
        year = attrs.get("year") if isinstance(attrs.get("year"), int) else None
        poster = None
        authors = []
        for rel in entry.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            rel_attrs = rel.get("attributes") or {}
            if rel.get("type") == "cover_art" and isinstance(rel_attrs, dict):
                filename = rel_attrs.get("fileName")
                if filename:
                    poster = f"{self.COVERS}/{manga_id}/{filename}"
            elif rel.get("type") == "author" and isinstance(rel_attrs, dict):
                author = rel_attrs.get("name")
                if author:
                    authors.append(str(author))
        if authors:
            byline = f"✍️ {', '.join(authors[:2])}"
            overview = f"{byline} — {overview}" if overview else byline
        return SearchResult(
            id=f"mangadex:{manga_id}",
            title=title,
            kind=MediaKind.ANIME,
            source_id=self.id,
            year=year,
            poster_url=poster,
            overview=overview,
            genres=tuple(tags[:10]),
        )

    def _query(self, params: dict[str, str]) -> list[SearchResult]:
        query = urllib.parse.urlencode(
            [("limit", "20"), ("includes[]", "cover_art"), ("includes[]", "author")]
            + [("contentRating[]", rating) for rating in self.RATINGS]
            + list(params.items())
        )
        try:
            data = _get_json(f"{self.api_url}/manga?{query}", self.timeout, self.proxy_url)
        except SourceError:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            return []
        results = []
        for entry in data["data"]:
            res = self._to_result(entry)
            if res is not None:
                results.append(res)
        return results

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        return self._query({"title": query, "order[relevance]": "desc"})

    def trending(self, limit: int = 20) -> list[SearchResult]:
        return self._query({"order[followedCount]": "desc"})[:limit]

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        return self._bridge_by_title(item.title, MediaKind.ANIME, number=episode.number)


class ITunesSource(BridgedCatalogueSource):
    """iTunes Store catalogue — movies and TV with poster art (free,
    keyless). Playback resolves through the stream addon by title."""

    id = "itunes"
    name = "iTunes (Movies & TV Catalogue)"

    API = "https://itunes.apple.com/search"
    KINDS = {
        "feature-movie": MediaKind.MOVIE,
        "tv-episode": MediaKind.SERIES,
        "tv-season": MediaKind.SERIES,
    }

    def __init__(
        self,
        api_url: str | None = None,
        stream_url: str | None = None,
        cinemeta_url: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
        source_id: str | None = None,
    ) -> None:
        super().__init__(
            stream_url=stream_url,
            cinemeta_url=cinemeta_url,
            timeout=timeout,
            proxy_url=proxy_url,
            source_id=source_id,
        )
        self.api_url = (api_url or self.API).rstrip("/")

    def _to_result(self, row: dict) -> SearchResult | None:
        if not isinstance(row, dict):
            return None
        kind = self.KINDS.get(str(row.get("kind", "")))
        if kind is None:
            return None
        track_id = row.get("trackId") or row.get("collectionId")
        if track_id is None:
            return None
        title = str(row.get("trackName") or row.get("collectionName") or "").strip()
        if not title:
            return None
        art = str(row.get("artworkUrl100", "") or "")
        poster = art.replace("100x100bb", "600x600bb") if art else None
        released = str(row.get("releaseDate", "") or "")
        year = int(released[:4]) if released[:4].isdigit() else None
        genre = str(row.get("primaryGenreName", "") or "")
        overview = str(row.get("longDescription") or row.get("shortDescription") or "")[:300]
        return SearchResult(
            id=f"itunes:{track_id}",
            title=title,
            kind=kind,
            source_id=self.id,
            year=year,
            poster_url=poster,
            overview=overview,
            genres=(genre,) if genre else (),
        )

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        params = urllib.parse.urlencode({"term": query, "limit": "25"})
        try:
            data = _get_json(f"{self.api_url}?{params}", self.timeout, self.proxy_url)
        except SourceError:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return []
        results = []
        for row in data["results"]:
            res = self._to_result(row)
            if res is not None:
                results.append(res)
        return results

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        if item.kind == MediaKind.MOVIE:
            return self._bridge_by_title(item.title, MediaKind.MOVIE)
        return self._bridge_by_title(item.title, MediaKind.SERIES)
