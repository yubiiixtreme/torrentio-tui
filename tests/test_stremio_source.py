"""Tests for the Stremio (Cinemeta + Torrentio) source.

Network is fully mocked — these verify catalogue parsing, episode
mapping, stream parsing (direct url + infoHash magnet), and quality
ranking without hitting the live APIs (Torrentio Cloudflare-blocks
datacenter IPs anyway).
"""
from __future__ import annotations

import io
import json
import urllib.error

from torrentio_tui.models import Episode, MediaKind, SearchResult
from torrentio_tui.player import torrent as torrent_mod
from torrentio_tui.sources import stremio as stremio_mod
from torrentio_tui.sources.base import SourceError
from torrentio_tui.sources.stremio import StremioSource


class _FakeResp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _mock_urlopen_factory(routes: dict, monkeypatch):
    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        for prefix, payload in routes.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return _FakeResp(payload)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(stremio_mod.urllib.request, "urlopen", fake_urlopen)


def test_search_merges_movie_and_series(monkeypatch):
    routes = {
        "https://c/catalog/movie/top/search=q": {
            "metas": [{
                "id": "tt0111161", "name": "The Shawshank Redemption",
                "releaseInfo": "1994", "poster": "http://p/1.jpg",
                "description": "Hope.", "genres": ["Drama"],
            }]
        },
        "https://c/catalog/series/top/search=q": {
            "metas": [{
                "id": "tt0903747", "name": "Breaking Bad",
                "releaseInfo": "2008–2013", "genres": ["Drama"],
            }]
        },
    }
    _mock_urlopen_factory(routes, monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    results = src.search("q")
    assert len(results) == 2
    movie, series = results
    assert movie.id == "movie:tt0111161"
    assert movie.kind == MediaKind.MOVIE
    assert movie.year == 1994
    assert movie.poster_url == "http://p/1.jpg"
    assert series.id == "series:tt0903747"
    assert series.kind == MediaKind.SERIES
    assert series.year == 2008


def test_search_classifies_anime(monkeypatch):
    routes = {
        "https://c/catalog/movie/top/search=naruto": {"metas": []},
        "https://c/catalog/series/top/search=naruto": {
            "metas": [{
                "id": "tt0409591", "name": "Naruto",
                "releaseInfo": "2002", "genres": ["Animation", "Anime"],
            }]
        },
    }
    _mock_urlopen_factory(routes, monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    [item] = src.search("naruto")
    assert item.kind == MediaKind.ANIME
    assert item.id == "series:tt0409591"


def test_get_episodes_series(monkeypatch):
    routes = {
        "https://c/meta/series/tt0903747.json": {
            "meta": {"videos": [
                {"id": "tt0903747:1:2", "name": "Ep2", "season": 1,
                 "number": 2},
                {"id": "tt0903747:1:1", "name": "Pilot", "season": 1,
                 "number": 1},
            ]}
        }
    }
    _mock_urlopen_factory(routes, monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    item = SearchResult(id="series:tt0903747", title="Breaking Bad",
                        kind=MediaKind.SERIES, source_id="stremio")
    eps = src.get_episodes(item)
    assert [e.id for e in eps] == ["tt0903747:1:1", "tt0903747:1:2"]
    assert eps[0].season == 1 and eps[0].number == 1


def test_get_episodes_movie_returns_single(monkeypatch):
    routes = {
        "https://c/meta/movie/tt0111161.json": {"meta": {"videos": []}}
    }
    _mock_urlopen_factory(routes, monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    item = SearchResult(id="movie:tt0111161", title="Shawshank",
                        kind=MediaKind.MOVIE, source_id="stremio")
    [ep] = src.get_episodes(item)
    assert ep.id == item.id


def test_get_streams_direct_and_magnet_sorted(monkeypatch):
    routes = {
        "https://s/stream/movie/tt0111161.json": {
            "streams": [
                {"name": "YTS", "title": "720p 👤10 💾800 MB",
                 "infoHash": "ab" * 20, "fileIdx": 0},
                {"name": "RD", "title": "Shawshank 1080p BluRay",
                 "url": "https://debrid.example/file.mp4"},
                {"name": "CAM", "title": "CAM 👤500",
                 "infoHash": "cd" * 20},
            ]
        }
    }
    _mock_urlopen_factory(routes, monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    item = SearchResult(id="movie:tt0111161", title="Shawshank",
                        kind=MediaKind.MOVIE, source_id="stremio")
    streams = src.get_streams(item, Episode(id=item.id, title=item.title))
    assert len(streams) == 3
    # 1080p direct link ranks first.
    assert streams[0].url == "https://debrid.example/file.mp4"
    assert "1080" in streams[0].quality
    # Magnets become magnet: links with trackers.
    assert streams[1].url.startswith("magnet:?xt=urn:btih:")
    assert "tr=" in streams[1].url


def test_get_streams_empty_returns_empty(monkeypatch):
    _mock_urlopen_factory(
        {"https://s/stream/series/tt1:1:1.json": {"streams": []}},
        monkeypatch)
    src = StremioSource(cinemeta_url="https://c", stream_url="https://s")
    item = SearchResult(id="series:tt1", title="X",
                        kind=MediaKind.SERIES, source_id="stremio")
    assert src.get_streams(item, Episode(id="tt1:1:1", title="E1")) == []


def test_torrentio_403_gives_helpful_error(monkeypatch):
    err = urllib.error.HTTPError(
        "https://torrentio.strem.fun/stream/movie/tt1.json", 403,
        "Forbidden", {}, io.BytesIO(b""))
    _mock_urlopen_factory(
        {"https://torrentio.strem.fun": err}, monkeypatch)
    src = StremioSource(cinemeta_url="https://c",
                        stream_url="https://torrentio.strem.fun")
    item = SearchResult(id="movie:tt1", title="X",
                        kind=MediaKind.MOVIE, source_id="stremio")
    try:
        src.get_streams(item, Episode(id=item.id, title="X"))
    except SourceError as exc:
        assert "403" in str(exc)
    else:
        raise AssertionError("expected SourceError")


def test_magnet_detection_and_missing_streamer(monkeypatch):
    assert torrent_mod.is_torrent_link("magnet:?xt=urn:btih:abc")
    assert not torrent_mod.is_torrent_link("https://cdn.example/v.mp4")
    monkeypatch.setattr(torrent_mod.shutil, "which", lambda _: None)
    try:
        torrent_mod.play_magnet("magnet:?xt=urn:btih:abc", "T")
    except torrent_mod.TorrentStreamError as exc:
        assert "webtorrent" in str(exc).lower() or "debrid" in str(exc).lower()
    else:
        raise AssertionError("expected TorrentStreamError")
