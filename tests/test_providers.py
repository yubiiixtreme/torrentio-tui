"""Tests for the provider batch: catalogue sources (TVMaze/Jikan/Kitsu),
torrent-index sources (YTS/RARBG), subtitle providers + orchestration,
source categories, and theme persistence."""

from __future__ import annotations

import json
import urllib.request

import pytest

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources import registry
from torrentio_tui.sources.base import SourceError
from torrentio_tui.sources.catalogues import JikanSource, KitsuSource, TVMazeSource


class _FakeHTTPResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(handler):
    """handler(url: str) -> payload; inspects the request URL."""

    def _opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        return _FakeHTTPResponse(handler(url))

    return _opener


def _cfg(**kwargs) -> Config:
    cfg = Config()
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


# -- TVMaze -------------------------------------------------------------------


def _tvmaze_search_payload():
    return [
        {
            "score": 1.0,
            "show": {
                "id": 1,
                "name": "Breaking Bad",
                "premiered": "2008-01-20",
                "summary": "<p>A chemistry teacher turns cook.</p>",
                "genres": ["Drama", "Crime"],
                "externals": {"imdb": "tt0903747"},
                "image": {"medium": "http://img/med.jpg"},
                "rating": {"average": 9.2},
            },
        }
    ]


def test_tvmaze_search_parses_show(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", _fake_urlopen(lambda url: _tvmaze_search_payload())
    )
    (result,) = TVMazeSource().search("breaking bad")
    assert result.id == "tvmaze:1"
    assert result.title == "Breaking Bad"
    assert result.year == 2008
    assert result.kind == MediaKind.SERIES
    assert "chemistry teacher" in (result.overview or "")
    assert "<p>" not in (result.overview or "")


def test_tvmaze_episodes_sorted(monkeypatch):
    payload = [
        {"id": 3, "name": "C", "season": 1, "number": 3},
        {"id": 1, "name": "A", "season": 1, "number": 1},
        {"id": 2, "name": "B", "season": 1, "number": 2},
    ]
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(lambda url: payload))
    item = SearchResult(id="tvmaze:1", title="BB", kind=MediaKind.SERIES, source_id="tvmaze")
    episodes = TVMazeSource().get_episodes(item)
    assert [e.number for e in episodes] == [1, 2, 3]
    assert episodes[0].title.startswith("S01E01")


def test_tvmaze_streams_bridge_via_imdb(monkeypatch):
    source = TVMazeSource()
    source._shows[1] = {"externals": {"imdb_id": "tt0903747"}}
    captured: dict = {}

    def _fake_streams(item, episode):
        captured["item_id"] = item.id
        captured["episode_id"] = episode.id
        return [StreamLink(url="https://cdn/x.mp4", quality="1080p")]

    monkeypatch.setattr(source._streams, "get_streams", _fake_streams)
    item = SearchResult(id="tvmaze:1", title="BB", kind=MediaKind.SERIES, source_id="tvmaze")
    links = source.get_streams(item, Episode(id="tvmaze:1:9", title="E", season=2, number=5))
    assert len(links) == 1
    assert captured["item_id"] == "series:tt0903747"
    assert captured["episode_id"] == "tt0903747:2:5"


def test_tvmaze_streams_falls_back_to_title_bridge(monkeypatch):
    source = TVMazeSource()
    source._shows[1] = {"externals": {}}  # no imdb -> title resolve
    candidate = SearchResult(
        id="series:tt0903747", title="Breaking Bad", kind=MediaKind.SERIES, source_id="x"
    )
    monkeypatch.setattr(source._streams, "search", lambda q: [candidate])
    monkeypatch.setattr(
        source._streams,
        "get_episodes",
        lambda item: [Episode(id="tt0903747:1:1", title="Pilot", season=1, number=1)],
    )
    monkeypatch.setattr(
        source._streams,
        "get_streams",
        lambda item, ep: [StreamLink(url="https://cdn/x.mp4", quality="720p")],
    )
    item = SearchResult(
        id="tvmaze:1", title="Breaking Bad", kind=MediaKind.SERIES, source_id="tvmaze"
    )
    links = source.get_streams(item, Episode(id="tvmaze:1:7", title="E", season=1, number=1))
    assert [link.quality for link in links] == ["720p"]


# -- Jikan --------------------------------------------------------------------


def _jikan_router(url: str):
    if "/anime?q=" in url:
        return {
            "data": [
                {
                    "mal_id": 21,
                    "title": "One Piece",
                    "title_english": "One Piece",
                    "type": "TV",
                    "images": {"jpg": {"image_url": "http://img/op.jpg"}},
                    "synopsis": "Pirates.",
                    "aired": {"prop": {"from": {"year": 1999}}},
                    "genres": [{"name": "Adventure"}],
                    "score": 8.9,
                }
            ]
        }
    if "/episodes" in url:
        return {"data": [{"episode": 2, "title": "Second"}], "pagination": {"has_next_page": False}}
    raise AssertionError(f"unexpected url {url}")


def test_jikan_search_and_episodes_and_bridge(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_jikan_router))
    source = JikanSource()
    (result,) = source.search("one piece")
    assert result.id == "jikan:21"
    assert result.kind == MediaKind.ANIME
    assert result.year == 1999

    episodes = source.get_episodes(result)
    assert episodes[0].number == 2
    assert episodes[0].season == 1

    candidate = SearchResult(
        id="series:tt999", title="One Piece", kind=MediaKind.SERIES, source_id="x"
    )
    monkeypatch.setattr(source._streams, "search", lambda q: [candidate])
    monkeypatch.setattr(
        source._streams,
        "get_episodes",
        lambda item: [Episode(id="tt999:1:2", title="E2", season=1, number=2)],
    )
    monkeypatch.setattr(
        source._streams,
        "get_streams",
        lambda item, ep: [StreamLink(url="https://cdn/x.mp4", quality="1080p")],
    )
    links = source.get_streams(result, episodes[0])
    assert len(links) == 1


# -- Kitsu --------------------------------------------------------------------


def _kitsu_router(url: str):
    if "/anime?filter" in url:
        return {
            "data": [
                {
                    "id": "41370",
                    "attributes": {
                        "canonicalTitle": "Attack on Titan",
                        "titles": {"en": "Attack on Titan"},
                        "posterImage": {"medium": "http://img/aot.jpg"},
                        "synopsis": "Titans.",
                        "startDate": "2013-04-07",
                        "showType": "TV",
                        "averageRating": "84.5",
                    },
                }
            ]
        }
    if "/episodes" in url:
        if "[offset]=0" in url:
            return {"data": [{"attributes": {"number": 1, "canonicalTitle": "First"}}]}
        return {"data": []}
    raise AssertionError(f"unexpected url {url}")


def test_kitsu_search_and_episodes_and_bridge(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_kitsu_router))
    source = KitsuSource()
    (result,) = source.search("attack on titan")
    assert result.id == "kitsu:41370"
    assert result.kind == MediaKind.ANIME
    assert result.year == 2013

    episodes = source.get_episodes(result)
    assert [e.number for e in episodes] == [1]

    candidate = SearchResult(
        id="series:tt456", title="Attack on Titan", kind=MediaKind.SERIES, source_id="x"
    )
    monkeypatch.setattr(source._streams, "search", lambda q: [candidate])
    monkeypatch.setattr(
        source._streams,
        "get_episodes",
        lambda item: [Episode(id="tt456:1:1", title="E1", season=1, number=1)],
    )
    monkeypatch.setattr(
        source._streams,
        "get_streams",
        lambda item, ep: [StreamLink(url="https://cdn/x.mp4", quality="1080p")],
    )
    assert len(source.get_streams(result, episodes[0])) == 1


# -- YTS ----------------------------------------------------------------------


def _yts_router(url: str):
    if "list_movies" in url:
        return {
            "status": "ok",
            "data": {
                "movies": [
                    {
                        "id": 10,
                        "title": "Dune",
                        "year": 2021,
                        "medium_cover_image": "http://img/dune.jpg",
                        "summary": "Desert.",
                        "genres": ["Sci-Fi"],
                    }
                ]
            },
        }
    if "movie_details" in url:
        return {
            "status": "ok",
            "data": {
                "movie": {
                    "torrents": [
                        {"hash": "ABCDEF123456", "quality": "1080p", "seeds": 120, "size": "1.8 GB"}
                    ]
                }
            },
        }
    raise AssertionError(f"unexpected url {url}")


def test_yts_search_and_magnet_streams(monkeypatch):
    from torrentio_tui.sources.torrentapi import YTSSource

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_yts_router))
    source = YTSSource()
    (result,) = source.search("dune")
    assert result.id == "yts:10"
    assert result.kind == MediaKind.MOVIE
    assert result.year == 2021

    (link,) = source.get_streams(result, Episode(id=result.id, title=result.title))
    assert link.url.startswith("magnet:?xt=urn:btih:ABCDEF123456")
    assert "1080p" in link.quality
    assert "120" in link.quality


# -- RARBG --------------------------------------------------------------------


def _rarbg_router(url: str):
    if "get_token" in url:
        return {"token": "tok123"}
    return {
        "torrent_results": [
            {
                "title": "Dune.2021.1080p.BluRay",
                "category": "Movies/X264/1080",
                "download": "magnet:?xt=urn:btih:DEADBEEF",
                "seeders": 42,
                "size": "8.1 GB",
            }
        ]
    }


def test_rarbg_search_episodes_streams(monkeypatch):
    import time

    from torrentio_tui.sources.torrentapi import RARBGSource

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_rarbg_router))
    source = RARBGSource()
    source._last_call_at = time.monotonic()  # skip the 2s throttle in tests
    (result,) = source.search("dune")
    assert result.kind == MediaKind.MOVIE
    assert result.year == 2021

    source._last_call_at = 0.0
    (episode,) = source.get_episodes(result)
    assert episode.id == "magnet:?xt=urn:btih:DEADBEEF"

    (link,) = source.get_streams(result, episode)
    assert link.url.startswith("magnet:")
    assert "1080p" in link.quality


# -- subtitle providers -------------------------------------------------------


def test_subdb_hash_and_search(monkeypatch, tmp_path):
    from torrentio_tui.sources.subtitles import SubDBProvider, opensubtitles_hash

    video = tmp_path / "movie.mkv"
    video.write_bytes(b"x" * 200_000)
    digest = opensubtitles_hash(video)
    assert len(digest) == 32

    class _TextResponse:
        def read(self):
            return b"en,es"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _TextResponse())
    provider = SubDBProvider()
    files = provider.search("Movie", file_hash=digest)
    assert {f.lang for f in files} == {"eng", "spa"}
    assert all("download" in f.url and digest in f.url for f in files)


def test_subdb_without_hash_raises():
    from torrentio_tui.sources.subtitles import SubDBProvider

    with pytest.raises(SourceError):
        SubDBProvider().search("Movie")


def test_opensubtitles_without_key_raises():
    from torrentio_tui.sources.subtitles import OpenSubtitlesProvider

    with pytest.raises(SourceError, match="API key"):
        OpenSubtitlesProvider().search("Movie", imdb_id="tt123")


def test_opensubtitles_search_and_download(monkeypatch):
    from torrentio_tui.sources.subtitles import OpenSubtitlesProvider

    provider = OpenSubtitlesProvider(api_key="key", username="u", password="p")
    calls: list = []

    def _fake_request(method, path, payload=None):
        calls.append((method, path))
        if path == "/login":
            return {"token": "tok"}
        assert "imdb_id=123" in path
        return {
            "data": [
                {"attributes": {"language": "en", "files": [{"file_id": 7, "file_name": "m.srt"}]}}
            ]
        }

    monkeypatch.setattr(provider, "_request", _fake_request)
    (sub,) = provider.search("Movie", imdb_id="tt123")
    assert sub.lang == "eng"
    assert sub.url == "7"

    def _fake_dl(method, path, payload=None):
        assert payload == {"file_id": 7}
        return {"link": "https://dl.os/m.srt"}

    monkeypatch.setattr(provider, "_request", _fake_dl)
    assert provider.download_url(sub) == "https://dl.os/m.srt"


def test_attach_subtitles_disabled_returns_unchanged():
    from torrentio_tui.sources.subtitles import attach_subtitles

    cfg = Config()  # [subtitles] disabled by default
    stream = StreamLink(url="https://cdn/x.mp4", quality="1080p")
    item = SearchResult(id="movie:tt123", title="M", kind=MediaKind.MOVIE, source_id="stremio")
    assert attach_subtitles(stream, item, Episode(id="x", title="M"), cfg) is stream


def test_attach_subtitles_picks_preferred_language(monkeypatch, tmp_path):
    import torrentio_tui.sources.subtitles as subs_mod
    from torrentio_tui.sources.subtitles import SubtitleFile, attach_subtitles

    cfg = Config()
    cfg.subtitles.enabled = True
    cfg.language.subtitle_languages = ["spa", "eng"]

    class _FakeProvider:
        id = "fake"

        def search(self, title, **kwargs):
            return [
                SubtitleFile(url="https://dl/a.srt", lang="eng", provider_id="fake"),
                SubtitleFile(url="https://dl/b.srt", lang="spa", provider_id="fake"),
            ]

        def download_url(self, sub):
            return sub.url

    monkeypatch.setattr(subs_mod, "load_subtitle_providers", lambda config: [_FakeProvider()])
    monkeypatch.setattr(
        subs_mod, "_download_to_cache", lambda url, key, lang, timeout, proxy: "/cache/b.srt"
    )
    stream = StreamLink(url="https://cdn/x.mp4", quality="1080p")
    item = SearchResult(id="movie:tt123", title="M", kind=MediaKind.MOVIE, source_id="stremio")
    out = attach_subtitles(stream, item, Episode(id="x", title="M"), cfg)
    assert out.subtitle_url == "/cache/b.srt"  # spa preferred over eng


def test_attach_subtitles_never_raises(monkeypatch):
    import torrentio_tui.sources.subtitles as subs_mod
    from torrentio_tui.sources.subtitles import attach_subtitles

    cfg = Config()
    cfg.subtitles.enabled = True
    monkeypatch.setattr(
        subs_mod,
        "load_subtitle_providers",
        lambda config: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    stream = StreamLink(url="https://cdn/x.mp4", quality="1080p")
    item = SearchResult(id="movie:tt123", title="M", kind=MediaKind.MOVIE, source_id="stremio")
    assert attach_subtitles(stream, item, Episode(id="x", title="M"), cfg) is stream


# -- categories / registry ----------------------------------------------------


def test_new_sources_registered_and_dead_ones_gone():
    ids = registry.available_source_ids()
    for expected in (
        "aiostreams",
        "stremthru",
        "jackettio",
        "nuviostreams",
        "deflix",
        "stremify",
        "yts",
        "rarbg",
        "tvmaze",
        "jikan",
        "kitsu",
    ):
        assert expected in ids
    for removed in (
        "debridmediamanager",
        "eztv",
        "1337x",
        "horriblesubs",
        "subscene",
        "opensubtitles",
    ):
        assert removed not in ids


def test_every_source_has_a_known_category():
    grouped = registry.sources_by_category()
    assert set(grouped) <= set(registry.CATEGORIES) | {"general"}
    seen_ids = {sid for entries in grouped.values() for sid, _ in entries}
    assert seen_ids == set(registry.available_source_ids())
    adult_ids = {sid for sid, _ in grouped["adult"]}
    assert {"stremio-adult", "hanime", "nhentai", "rule34"} <= adult_ids


def test_catalogue_and_torrent_sources_load_with_proxy():
    cfg = Config()
    cfg.network.proxy_url = "http://127.0.0.1:8080"
    cfg.enabled_sources = ["tvmaze", "jikan", "kitsu", "yts", "rarbg"]
    by_id = {s.id: s for s in registry.load_sources(cfg)}
    assert set(by_id) == {"tvmaze", "jikan", "kitsu", "yts", "rarbg"}
    for source in by_id.values():
        assert source.proxy_url == "http://127.0.0.1:8080"


# -- theme persistence --------------------------------------------------------


@pytest.mark.asyncio
async def test_selected_theme_is_saved_for_next_launch(tmp_path, monkeypatch):
    import torrentio_tui.config as config_mod
    from torrentio_tui.sources.local import LocalSource
    from torrentio_tui.ui.app import TorrentioTuiApp

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ui]\ntheme = "torrentio"\n')
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg_file)

    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "torrentio"
        # Selecting a theme by any path (cycle key, Ctrl+P picker, ...)
        # persists it through the watcher.
        app.theme = "dracula"
        await pilot.pause()
        assert app.config.ui.theme == "dracula"
    assert 'theme = "dracula"' in cfg_file.read_text()


# -- cli ----------------------------------------------------------------------


def test_list_sources_groups_by_category(capsys):
    from torrentio_tui.cli import main

    assert main(["--list-sources"]) == 0
    out = capsys.readouterr().out
    assert "[Streams]" in out
    assert "aiostreams" in out
    assert "[Adult (opt-in)]" in out
