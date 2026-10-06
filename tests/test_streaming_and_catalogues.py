"""Tests for the streaming/seek, adult-fix, catalogue, and poster batch.

Covers: mpv/vlc instant-start + seek flags, direct-first stream ranking,
E-Hentai two-step search, Hanime bridge (in test_robustness), Sukebei RSS,
MangaDex/iTunes catalogue parsing with posters, Rule34 auth params,
registry wiring (sukebei/mangadex/itunes in, hentaihaven out), and
catalogue-row poster thumbnails.
"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
import urllib.request

import pytest

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.sources import registry
from torrentio_tui.sources.base import SourceError


def _adult_config() -> Config:
    cfg = Config()
    cfg.adult.enabled = True
    return cfg


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _json_response(payload: object):
    def _opener(request, timeout=None):
        return _FakeHTTPResponse(json.dumps(payload).encode())

    return _opener


# -- streaming flags ----------------------------------------------------------


def test_mpv_direct_http_gets_streaming_flags(monkeypatch):
    from torrentio_tui.player import mpv as mpv_mod

    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mpv_mod, "run_supervised", fake_run)
    mpv_mod.MpvPlayer(hwdec="").play(
        StreamLink(url="https://cdn.example.com/ep1.mp4", quality="1080p"), "Ep 1"
    )
    assert "--cache=yes" in captured["cmd"]
    assert "--demuxer-readahead-secs=15" in captured["cmd"]
    assert "--force-seekable=yes" in captured["cmd"]
    assert captured["cmd"][-1] == "https://cdn.example.com/ep1.mp4"


def test_mpv_live_stream_skips_seek_flags(monkeypatch):
    from torrentio_tui.player import mpv as mpv_mod

    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mpv_mod, "run_supervised", fake_run)
    mpv_mod.MpvPlayer(hwdec="").play(
        StreamLink(url="https://cdn.example.com/live.m3u8", quality="auto", is_live=True),
        "Live",
    )
    assert not any(
        c.startswith(("--cache", "--demuxer", "--force-seekable")) for c in captured["cmd"]
    )


def test_mpv_streaming_args_share_with_hud():
    from torrentio_tui.player.mpv import streaming_args

    direct = StreamLink(url="https://cdn.example.com/a.mp4", quality="1080p")
    live = StreamLink(url="https://cdn.example.com/l.m3u8", quality="auto", is_live=True)
    local = StreamLink(url="/home/user/Videos/a.mp4", quality="1080p")
    assert streaming_args(direct) == [
        "--cache=yes",
        "--demuxer-readahead-secs=15",
        "--force-seekable=yes",
    ]
    assert streaming_args(live) == []
    assert streaming_args(local) == []


def test_vlc_caches_on_demand_http_only(monkeypatch):
    from torrentio_tui.player import vlc as vlc_mod

    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(vlc_mod, "run_supervised", fake_run)
    vlc_mod.VlcPlayer().play(StreamLink(url="https://cdn.example.com/a.mp4", quality="720p"), "T")
    assert "--network-caching=3000" in captured["cmd"]
    vlc_mod.VlcPlayer().play(
        StreamLink(url="https://cdn.example.com/l.m3u8", quality="auto", is_live=True), "L"
    )
    assert "--network-caching=3000" not in captured["cmd"]


def test_ranked_streams_direct_first_magnets_last():
    from torrentio_tui.ui.screens.quality import QualityScreen, ranked_streams

    magnet = StreamLink(url="magnet:?xt=urn:btih:abc", quality="magnet")
    direct = StreamLink(url="https://cdn.example.com/a.mp4", quality="1080p")
    local = StreamLink(url="/home/user/Videos/a.mp4", quality="1080p")
    assert ranked_streams([magnet, local, direct]) == [direct, local, magnet]
    screen = QualityScreen([magnet, direct])
    assert screen.streams[0] == direct
    assert screen.streams[-1] == magnet


# -- E-Hentai two-step search -------------------------------------------------


EHENTAI_HTML = (
    "<html><body>"
    '<a href="https://e-hentai.org/g/111/aaaaaaaaaa/">one</a>'
    '<a href="https://e-hentai.org/g/222/bbbbbbbbbb/">two</a>'
    '<a href="https://e-hentai.org/g/111/aaaaaaaaaa/">dup</a>'
    "</body></html>"
)

EHENTAI_GDATA = {
    "gmetadata": [
        {
            "gid": 111,
            "token": "aaaaaaaaaa",
            "title": "Gallery One",
            "title_jpn": "",
            "category": "Doujinshi",
            "tags": ["artist:one", "female:big"],
            "thumb": "",
        },
        {
            "gid": 222,
            "token": "bbbbbbbbbb",
            "title": "Gallery Two",
            "title_jpn": "",
            "category": "Manga",
            "tags": [],
            "thumb": "",
        },
    ]
}


def test_ehentai_search_scrapes_ids_then_gdata(monkeypatch):
    from torrentio_tui.sources.adult_extended import EHentaiSource

    seen_urls: list[str] = []

    def _opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        seen_urls.append(url)
        if "api.e-hentai.org" in url:
            return _FakeHTTPResponse(json.dumps(EHENTAI_GDATA).encode())
        return _FakeHTTPResponse(EHENTAI_HTML.encode())

    monkeypatch.setattr(urllib.request, "urlopen", _opener)
    results = EHentaiSource(config=_adult_config()).search("test")
    assert len(results) == 2  # duplicate link deduped
    assert results[0].id == "ehentai:111:aaaaaaaaaa"
    assert results[0].poster_url  # thumbnail built from gid/token
    assert "one" in results[0].genres
    assert any("api.e-hentai.org" in u for u in seen_urls)
    assert any("f_search=test" in u for u in seen_urls)


def test_ehentai_search_no_links_returns_empty(monkeypatch):
    from torrentio_tui.sources.adult_extended import EHentaiSource

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=None: _FakeHTTPResponse(b"<html></html>")
    )
    assert EHentaiSource(config=_adult_config()).search("zzz-no-match") == []


# -- Sukebei ------------------------------------------------------------------


SUKEBEI_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Sukebei</title>
<item><title>[ABC] Show Title S01E01 [1080p]</title>
<link>https://sukebei.nyaa.si/download/123.torrent</link>
<description>Size: 1.4 GiB | Seeders: 42</description></item>
<item><title>No link here</title></item>
</channel></rss>"""


def test_sukebei_rss_search(monkeypatch):
    from torrentio_tui.sources.adult_extended import SukebeiSource

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=None: _FakeHTTPResponse(SUKEBEI_RSS.encode())
    )
    source = SukebeiSource(config=_adult_config())
    assert source.category == "adult"
    assert source.search("") == []
    results = source.search("show")
    assert len(results) == 1
    assert results[0].id == "sukebei:https://sukebei.nyaa.si/download/123.torrent"
    assert "42" in (results[0].overview or "")
    links = source.get_streams(results[0], Episode(id=results[0].id, title="t"))
    assert len(links) == 1
    assert links[0].url.endswith(".torrent")


def test_sukebei_gated_without_adult_enabled():
    from torrentio_tui.sources.adult_extended import SukebeiSource

    with pytest.raises(SourceError):
        SukebeiSource(config=Config())


# -- MangaDex / iTunes --------------------------------------------------------


MANGADEX_PAYLOAD = {
    "data": [
        {
            "id": "manga-1",
            "attributes": {
                "title": {"en": "Test Manga"},
                "description": {"en": "A test manga."},
                "tags": [{"attributes": {"name": {"en": "Action"}}}],
                "year": 2020,
            },
            "relationships": [
                {"type": "cover_art", "attributes": {"fileName": "cover.jpg"}},
                {"type": "author", "attributes": {"name": "Some Author"}},
            ],
        },
        {"id": "", "attributes": {}},  # skipped: no usable title
    ]
}


def test_mangadex_search_has_covers(monkeypatch):
    from torrentio_tui.sources.catalogues import MangaDexSource

    seen: list[str] = []

    def _opener(request, timeout=None):
        seen.append(request.full_url if hasattr(request, "full_url") else str(request))
        return _FakeHTTPResponse(json.dumps(MANGADEX_PAYLOAD).encode())

    monkeypatch.setattr(urllib.request, "urlopen", _opener)
    source = MangaDexSource()
    results = source.search("test")
    assert len(results) == 1
    assert results[0].title == "Test Manga"
    assert results[0].poster_url == "https://uploads.mangadex.org/covers/manga-1/cover.jpg"
    assert results[0].year == 2020
    assert "Action" in results[0].genres
    assert "Some Author" in (results[0].overview or "")
    assert "contentRating" in seen[0]  # general catalogue stays clean
    assert source.search("   ") == []


def test_mangadex_trending_respects_limit(monkeypatch):
    from torrentio_tui.sources.catalogues import MangaDexSource

    monkeypatch.setattr(urllib.request, "urlopen", _json_response(MANGADEX_PAYLOAD))
    results = MangaDexSource().trending(limit=1)
    assert len(results) == 1


ITUNES_PAYLOAD = {
    "resultCount": 3,
    "results": [
        {
            "kind": "feature-movie",
            "trackId": 1,
            "trackName": "Test Movie",
            "artworkUrl100": "https://example.com/a/100x100bb.jpg",
            "releaseDate": "2019-05-01T07:00:00Z",
            "primaryGenreName": "Action",
            "longDescription": "Boom.",
        },
        {
            "kind": "tv-season",
            "collectionId": 2,
            "collectionName": "Test Show",
            "artworkUrl100": "https://example.com/b/100x100bb.jpg",
            "releaseDate": "2020-01-01T08:00:00Z",
            "primaryGenreName": "Drama",
            "shortDescription": "Episodes.",
        },
        {"kind": "song", "trackId": 3, "trackName": "Not media"},
    ],
}


def test_itunes_search_filters_and_upgrades_art(monkeypatch):
    from torrentio_tui.sources.catalogues import ITunesSource

    monkeypatch.setattr(urllib.request, "urlopen", _json_response(ITUNES_PAYLOAD))
    results = ITunesSource().search("test")
    assert len(results) == 2  # song row dropped
    movie, show = results
    assert movie.kind == MediaKind.MOVIE
    assert movie.year == 2019
    assert movie.id.startswith("itunes:movie:")
    assert movie.poster_url == "https://example.com/a/600x600bb.jpg"
    assert show.kind == MediaKind.SERIES
    assert show.year == 2020
    assert show.id.startswith("itunes:tv:")
    assert ITunesSource().search("  ") == []


# -- Rule34 auth --------------------------------------------------------------


def test_rule34_appends_configured_credentials(monkeypatch):
    from torrentio_tui.sources.adult import Rule34Source

    cfg = _adult_config()
    cfg.sources_config["rule34"] = {"api_key": "KEY", "user_id": "7"}
    seen: list[str] = []

    def _opener(request, timeout=None):
        seen.append(request.full_url if hasattr(request, "full_url") else str(request))
        return _FakeHTTPResponse(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", _opener)
    assert Rule34Source(config=cfg).search("test") == []
    assert "api_key=KEY" in seen[0]
    assert "user_id=7" in seen[0]


def test_rule34_401_points_at_credentials(monkeypatch):
    from torrentio_tui.sources.adult import Rule34Source

    def _opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", _opener)
    with pytest.raises(SourceError, match="api_key"):
        Rule34Source(config=_adult_config()).search("test")


# -- adult catalogues: hentaimanga / anilist-adult / hanime trending --------


def test_hentaimanga_serves_pornographic_with_covers(monkeypatch):
    from torrentio_tui.sources.adult_extended import HentaiMangaSource

    seen: list[str] = []

    def _opener(request, timeout=None):
        seen.append(request.full_url if hasattr(request, "full_url") else str(request))
        return _FakeHTTPResponse(json.dumps(MANGADEX_PAYLOAD).encode())

    monkeypatch.setattr(urllib.request, "urlopen", _opener)
    source = HentaiMangaSource(config=_adult_config())
    assert source.category == "adult"
    assert source.RATINGS == ("pornographic",)
    results = source.search("test")
    assert len(results) == 1
    assert results[0].source_id == "hentaimanga"
    assert results[0].id.startswith("hentaimanga:")
    assert results[0].poster_url is not None
    assert "contentRating%5B%5D=pornographic" in seen[0] or "contentRating" in seen[0]
    assert source.search("  ") == []


def test_hentaimanga_gated_and_proxy_honored():
    from torrentio_tui.sources.adult_extended import HentaiMangaSource

    with pytest.raises(SourceError):
        HentaiMangaSource(config=Config())
    cfg = _adult_config()
    cfg.network.proxy_url = "http://127.0.0.1:8080"
    assert HentaiMangaSource(config=cfg).proxy_url == "http://127.0.0.1:8080"


ANILIST_ADULT_PAYLOAD = {
    "data": {
        "Page": {
            "media": [
                {
                    "id": 999,
                    "title": {"romaji": "Adult Test", "english": None, "native": "テスト"},
                    "type": "ANIME",
                    "format": "OVA",
                    "status": "FINISHED",
                    "description": "Desc.",
                    "startDate": {"year": 2022},
                    "season": None,
                    "seasonYear": None,
                    "genres": ["Hentai"],
                    "averageScore": 70,
                    "episodes": 2,
                    "coverImage": {"large": "https://cdn.example.com/cover.jpg"},
                    "isAdult": True,
                }
            ]
        }
    }
}


def test_anilist_adult_search_with_covers(monkeypatch):
    from torrentio_tui.sources.adult_extended import AnilistAdultSource

    monkeypatch.setattr(urllib.request, "urlopen", _json_response(ANILIST_ADULT_PAYLOAD))
    source = AnilistAdultSource(config=_adult_config())
    assert source.category == "adult"
    results = source.search("test")
    assert len(results) == 1
    assert results[0].source_id == "anilist-adult"
    assert results[0].poster_url == "https://cdn.example.com/cover.jpg"
    assert results[0].year == 2022
    assert source.search("   ") == []


def test_anilist_adult_gated():
    from torrentio_tui.sources.adult_extended import AnilistAdultSource

    with pytest.raises(SourceError):
        AnilistAdultSource(config=Config())


def test_hanime_trending_returns_likes_chart(monkeypatch):
    from torrentio_tui.sources.adult import HanimeSource

    payload = {
        "data": [
            {
                "id": i,
                "name": f"Show {i}",
                "slug": f"show-{i}",
                "poster_url": f"https://cdn.example.com/p{i}.jpg",
                "description": "",
                "tags": [],
                "brand": "",
                "released_at": "",
            }
            for i in range(5)
        ]
    }
    monkeypatch.setattr(urllib.request, "urlopen", _json_response(payload))
    results = HanimeSource(config=_adult_config()).trending(limit=2)
    assert len(results) == 2
    assert all(r.poster_url for r in results)


# -- registry -----------------------------------------------------------------


def test_registry_new_ids_and_retired_hentaihaven():
    ids = registry.available_source_ids()
    assert {"sukebei", "mangadex", "itunes", "hentaimanga", "anilist-adult"} <= set(ids)
    assert "hentaihaven" not in ids
    grouped = registry.sources_by_category()
    assert {"sukebei", "hentaimanga", "anilist-adult"} <= {sid for sid, _ in grouped["adult"]}
    assert "mangadex" in {sid for sid, _ in grouped["catalogue"]}
    assert "itunes" in {sid for sid, _ in grouped["catalogue"]}


def test_adult_sources_load_with_caller_config():
    cfg = _adult_config()
    cfg.enabled_sources = ["hentaimanga", "anilist-adult", "hanime", "sukebei"]
    loaded = registry.load_sources(cfg)
    assert {s.id for s in loaded} == {"hentaimanga", "anilist-adult", "hanime", "sukebei"}


def test_adult_gate_blocks_registry_load():
    cfg = Config()  # adult disabled
    cfg.enabled_sources = ["hentaimanga", "anilist-adult"]
    with pytest.raises(SourceError):
        registry.load_sources(cfg)


def test_new_catalogues_load_with_proxy():
    cfg = Config()
    cfg.network.proxy_url = "http://127.0.0.1:8080"
    cfg.enabled_sources = ["mangadex", "itunes"]
    loaded = registry.load_sources(cfg)
    assert {s.id for s in loaded} == {"mangadex", "itunes"}
    assert all(s.proxy_url == "http://127.0.0.1:8080" for s in loaded)


def test_itunes_has_no_trending_feed_by_default():
    from torrentio_tui.sources.catalogues import ITunesSource

    assert ITunesSource().trending(limit=5) == []


# -- poster rows --------------------------------------------------------------


def test_result_item_thumb_cap_and_marker():
    import torrentio_tui.ui.screens.main as main_mod

    assert main_mod.MAX_ROW_THUMBS == 12

    def _item(i: int) -> SearchResult:
        return SearchResult(
            id=f"x:{i}",
            title=f"Title {i}",
            kind=MediaKind.MOVIE,
            source_id="stremio",
            poster_url=f"https://example.com/p{i}.jpg",
        )

    rows = [main_mod.ResultItem(_item(i), thumb=i < main_mod.MAX_ROW_THUMBS) for i in range(14)]
    with_poster = [r for r in rows if r.thumb is not None]
    assert len(with_poster) == (12 if main_mod.IMAGES_AVAILABLE else 0)
    # Every poster row is still identifiable without the live thumbnail.
    assert rows[13].thumb is None


def test_result_item_without_poster_has_no_thumb_box():
    import torrentio_tui.ui.screens.main as main_mod

    item = SearchResult(id="x:1", title="No Art", kind=MediaKind.MOVIE, source_id="stremio")
    assert main_mod.ResultItem(item, thumb=True).thumb is None


def test_show_thumb_is_safe_unmounted(tmp_path):
    import torrentio_tui.ui.screens.main as main_mod

    item = SearchResult(
        id="x:1",
        title="Art",
        kind=MediaKind.MOVIE,
        source_id="stremio",
        poster_url="https://example.com/p.jpg",
    )
    row = main_mod.ResultItem(item, thumb=True)
    row.show_thumb(tmp_path / "p.jpg", "https://example.com/p.jpg")  # must not raise
    row.show_thumb(tmp_path / "p.jpg", "https://example.com/other.jpg")  # stale: ignored
