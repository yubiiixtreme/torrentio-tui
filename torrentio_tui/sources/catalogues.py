"""Metadata catalogue sources: TVMaze, Jikan (MyAnimeList), Kitsu.

These are *discovery* companions, not stream indexes — all three APIs are
free and keyless, and each is stronger than Cinemeta somewhere (TVMaze
for series air-dates/episodes, Jikan/Kitsu for anime depth). To avoid
the classic dead-end catalogue (results that can never play), every
source here bridges to playable streams through a Stremio-protocol
stream addon — TVMaze via the show's IMDb external id when available,
otherwise (and for Jikan/Kitsu) via a Cinemeta title resolve — so the
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


def _get_json(url: str, timeout: float, proxy_url: str | None):
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    try:
        import json

        with open_url(url, timeout, proxy_url, headers) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except ProxyError as exc:
        raise SourceError(str(exc)) from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise SourceError(f"Request failed (HTTP {exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise SourceError(f"Network error for {url}: {exc.reason}") from exc
    except (ValueError, TimeoutError) as exc:
        raise SourceError(f"Bad response from {url}: {exc}") from exc


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
            data = _get_json(f"{self.api_url}/shows/{show_id}", self.timeout, self.proxy_url)
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
        return _get_json(f"{self.api_url}{path}", self.timeout, self.proxy_url)

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
