"""Tests for the remake: funnel filters, trending, settings saves,
new sources, episode season-jump."""

from __future__ import annotations

import re

import pytest

from torrentio_tui.models import Episode, MediaKind, SearchResult
from torrentio_tui.ui.screens.main import (
    SORT_OPTIONS,
    YEAR_OPTIONS,
    _year_matches,
    apply_result_filters,
)


def _result(
    title: str,
    kind: MediaKind = MediaKind.MOVIE,
    source_id: str = "stremio",
    year: int | None = None,
    genres: tuple[str, ...] = (),
    overview: str = "",
) -> SearchResult:
    return SearchResult(
        id=f"{source_id}:{title}",
        title=title,
        kind=kind,
        source_id=source_id,
        year=year,
        overview=overview,
        genres=genres,
    )


# -- year buckets -----------------------------------------------------------


def test_year_matches_buckets() -> None:
    assert _year_matches(2024, "Any year")
    assert _year_matches(None, "Any year")
    assert _year_matches(2024, "2024")
    assert not _year_matches(2023, "2024")
    assert not _year_matches(None, "2024")
    assert _year_matches(2021, "2020s")
    assert not _year_matches(2019, "2020s")
    assert _year_matches(1999, "Classic (<2000)")
    assert not _year_matches(2000, "Classic (<2000)")
    assert _year_matches(2015, "2010s")
    assert _year_matches(2005, "2000s")


def test_filter_option_constants_sane() -> None:
    assert YEAR_OPTIONS[0] == "Any year"
    assert SORT_OPTIONS[0] == "Relevance"
    assert len(SORT_OPTIONS) == 4


# -- funnel -----------------------------------------------------------------


def test_funnel_kind_filter() -> None:
    results = [
        _result("A", MediaKind.MOVIE),
        _result("B", MediaKind.SERIES),
    ]
    assert [r.title for r in apply_result_filters(results, kind="Movie")] == ["A"]
    assert [r.title for r in apply_result_filters(results, kind="All")] == ["A", "B"]


def test_funnel_category_filter() -> None:
    results = [_result("A", source_id="stremio"), _result("B", source_id="nyaa")]
    assert [r.title for r in apply_result_filters(results, category="Anime")] == ["B"]
    assert len(apply_result_filters(results, category="All")) == 2


def test_funnel_genre_matches_genres_title_overview() -> None:
    results = [
        _result("Dune", genres=("Action", "Adventure")),
        _result("Barkhan", overview="a desert adventure"),
        _result("Comedy Night", genres=("Comedy",)),
    ]
    assert [r.title for r in apply_result_filters(results, genre="adventure")] == [
        "Dune",
        "Barkhan",
    ]
    assert apply_result_filters(results, genre="  ") == results


def test_funnel_year_and_sort() -> None:
    results = [
        _result("Old", year=1999),
        _result("Mid", year=2015),
        _result("New", year=2024),
        _result("Unknown", year=None),
    ]
    assert [r.title for r in apply_result_filters(results, year="2020s")] == ["New"]
    assert [r.title for r in apply_result_filters(results, year="Classic (<2000)")] == ["Old"]
    assert [r.title for r in apply_result_filters(results, sort="Newest first")] == [
        "New",
        "Mid",
        "Old",
        "Unknown",
    ]
    assert [r.title for r in apply_result_filters(results, sort="Oldest first")] == [
        "Old",
        "Mid",
        "New",
        "Unknown",
    ]
    assert [r.title for r in apply_result_filters(results, sort="Title A–Z")] == [
        "Mid",
        "New",
        "Old",
        "Unknown",
    ]
    # Relevance keeps original order
    assert [r.title for r in apply_result_filters(results)] == ["Old", "Mid", "New", "Unknown"]


# -- trending ---------------------------------------------------------------


def test_trending_defaults_to_empty() -> None:
    from torrentio_tui.sources.local import LocalSource

    assert LocalSource(root="/tmp").trending() == []


def test_stremio_trending_uses_top_catalogs(monkeypatch) -> None:
    from torrentio_tui.sources.stremio import StremioSource

    source = StremioSource()
    monkeypatch.setattr(
        source,
        "_catalog",
        lambda stype, query: [
            {
                "id": "tt123",
                "name": "Top Thing",
                "genres": ["Action"],
                "releaseInfo": "2024",
                "poster": None,
                "description": "great",
            }
        ],
    )
    results = source.trending(limit=5)
    assert len(results) == 2  # movie + series catalogs
    assert results[0].title == "Top Thing"
    assert results[0].year == 2024
    assert all(r.source_id == "stremio" for r in results)


# -- new sources ------------------------------------------------------------


def test_new_sources_registered() -> None:
    from torrentio_tui.sources import registry

    ids = registry.available_source_ids()
    for expected in (
        "limetorrents",
        "torrentdownloads",
        "glodls",
        "iptv-org",
        "anidex",
        "animetosho",
        "tokyotoshokan",
        "thepiratebay",
        "rarbg-mirror",
        "nyaa-torrents",
        "ehentai",
        "hitomila",
        "hentaihaven",
    ):
        assert expected in ids


def test_adult_sources_all_gated() -> None:
    from torrentio_tui.sources import registry

    grouped = registry.sources_by_category()
    adult_ids = {sid for sid, _ in grouped["adult"]}
    assert {
        "stremio-adult",
        "hanime",
        "nhentai",
        "rule34",
        "ehentai",
        "hitomila",
        "hentaihaven",
    } <= adult_ids


def test_rss_sources_empty_query_returns_empty() -> None:
    from torrentio_tui.sources.rss_indexes import (
        GloDLSSource,
        LimeTorrentsSource,
        TorrentDownloadsSource,
    )

    for cls in (LimeTorrentsSource, TorrentDownloadsSource, GloDLSSource):
        assert cls().search("") == []
        assert cls().search("   ") == []
        assert cls.category == "streams"


def test_tmdb_trakt_construct_without_crossed_kwargs() -> None:
    from torrentio_tui.config import Config
    from torrentio_tui.sources.registry import load_sources

    cfg = Config()
    cfg.enabled_sources = ["tmdb", "trakt"]
    by_id = {s.id: s for s in load_sources(cfg)}
    assert set(by_id) == {"tmdb", "trakt"}


# -- settings save helpers --------------------------------------------------


def test_save_adult_enabled_roundtrip(tmp_path, monkeypatch) -> None:
    import torrentio_tui.config as config_mod
    from torrentio_tui.config import save_adult_enabled

    cfg = tmp_path / "config.toml"
    cfg.write_text("[adult]\nenabled = false\n")
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_adult_enabled(True)
    assert "enabled = true" in cfg.read_text()
    save_adult_enabled(False)
    assert "enabled = false" in cfg.read_text()


def test_save_player_backend_roundtrip(tmp_path, monkeypatch) -> None:
    import torrentio_tui.config as config_mod
    from torrentio_tui.config import save_player_backend

    cfg = tmp_path / "config.toml"
    cfg.write_text('[player]\nbackend = "mpv"\n')
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_player_backend("vlc")
    assert 'backend = "vlc"' in cfg.read_text()


def test_save_subtitles_and_download_dir(tmp_path, monkeypatch) -> None:
    import torrentio_tui.config as config_mod
    from torrentio_tui.config import save_download_dir, save_subtitles_enabled

    cfg = tmp_path / "config.toml"
    cfg.write_text("[subtitles]\nenabled = false\n")
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_subtitles_enabled(True)
    assert "enabled = true" in cfg.read_text()
    save_download_dir("~/Movies")
    text = cfg.read_text()
    assert "[downloads]" in text
    assert 'directory = "~/Movies"' in text


# -- save-helper stability (no section glue, no dupes) ----------------------


def _assert_config_sane(text: str) -> None:
    for line in text.splitlines():
        # A value line glued onto a section header, e.g.
        # `theme = "void"[sources]`.
        assert not re.search(r".+\]\s*\[.+\]", line), f"glued line: {line!r}"
        assert not re.search(r"""["']\s*\[.+\]""", line), f"glued line: {line!r}"


def test_repeated_theme_saves_stay_stable(tmp_path, monkeypatch) -> None:
    import torrentio_tui.config as config_mod
    from torrentio_tui.config import _default_config_toml, save_theme

    cfg = tmp_path / "config.toml"
    cfg.write_text(_default_config_toml())
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    for theme in ("nord", "dracula", "matrix", "nord", "torrentio"):
        save_theme(theme)
    text = cfg.read_text()
    _assert_config_sane(text)
    assert text.count('theme = "') == 1
    assert "[sources]" in text


def test_repeated_source_and_setting_saves_stay_stable(tmp_path, monkeypatch) -> None:
    import torrentio_tui.config as config_mod
    from torrentio_tui.config import (
        _default_config_toml,
        save_adult_enabled,
        save_download_dir,
        save_enabled_sources,
        save_player_backend,
        save_subtitles_enabled,
    )

    cfg = tmp_path / "config.toml"
    cfg.write_text(_default_config_toml())
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    for _ in range(3):
        save_enabled_sources(["stremio", "yts"])
        save_enabled_sources(["stremio", "mediafusion", "comet", "local"])
        save_adult_enabled(True)
        save_adult_enabled(False)
        save_player_backend("vlc")
        save_player_backend("mpv")
        save_subtitles_enabled(True)
        save_download_dir("/tmp/x")
    text = cfg.read_text()
    _assert_config_sane(text)
    headers = [line for line in text.splitlines() if line.startswith("[")]
    assert headers.count("[adult]") == 1
    assert headers.count("[downloads]") == 1
    assert headers.count("[player]") == 1
    assert headers.count("[subtitles]") == 1
    assert headers.count("[sources]") == 1
    assert sum(1 for line in text.splitlines() if line.startswith("enabled = [")) == 1


# -- settings screen --------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_screen_opens_and_closes(tmp_path) -> None:
    from torrentio_tui.config import Config
    from torrentio_tui.sources.local import LocalSource
    from torrentio_tui.ui.app import TorrentioTuiApp
    from torrentio_tui.ui.screens.settings import SettingsScreen

    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.action_settings()
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)
        app.screen.action_close()
        await pilot.pause()
        assert not isinstance(app.screen, SettingsScreen)


# -- main screen funnel wiring ----------------------------------------------


@pytest.mark.asyncio
async def test_funnel_filters_rendered_results_without_network(tmp_path) -> None:
    from textual.widgets import Input, Select

    from torrentio_tui.config import Config
    from torrentio_tui.sources.local import LocalSource
    from torrentio_tui.ui.app import TorrentioTuiApp

    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen._last_results = [
            _result("Dune", MediaKind.MOVIE, year=2021, genres=("Sci-Fi",)),
            _result("Dune Series", MediaKind.SERIES, year=2024),
        ]
        screen.query_one("#filter-kind", Select).value = "Series"
        screen._apply_filters_and_render()
        await pilot.pause()
        children = screen.query_one("#search-results").children
        assert len(children) == 1
        assert children[0].item.title == "Dune Series"
        assert "1/2" in str(screen.query_one("#filter-count").render())
        screen.query_one("#filter-kind", Select).value = "All"
        screen.query_one("#filter-genre", Input).value = "sci-fi"
        screen._apply_filters_and_render()
        await pilot.pause()
        assert len(screen.query_one("#search-results").children) == 1


@pytest.mark.asyncio
async def test_funnel_toggle_hides_and_shows(tmp_path) -> None:
    from torrentio_tui.config import Config
    from torrentio_tui.sources.local import LocalSource
    from torrentio_tui.ui.app import TorrentioTuiApp

    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.screen.query_one("#filter-bar")
        assert bar.display
        app.screen.action_toggle_filters()
        await pilot.pause()
        assert not bar.display
        app.screen.action_toggle_filters()
        await pilot.pause()
        assert bar.display


# -- episode season jump ----------------------------------------------------


@pytest.mark.asyncio
async def test_episode_digit_jumps_to_season() -> None:
    from textual.app import App
    from textual.widgets import ListView

    from torrentio_tui.ui.screens.episodes import EpisodePicked, EpisodeScreen

    episodes = [
        Episode(id="s1e1", title="Pilot", season=1, number=1),
        Episode(id="s2e1", title="Alive", season=2, number=1),
        Episode(id="s2e2", title="Cherry", season=2, number=2),
    ]

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.push_screen(EpisodeScreen(episodes, title="Breaking Bad"))

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert "Breaking Bad" in str(screen.query_one("#episode-title").render())
        assert "3 episode" in str(screen.query_one("#episode-count").render())
        list_view = screen.query_one(ListView)
        list_view.focus()
        await pilot.press("2")
        await pilot.pause()
        assert isinstance(list_view.highlighted_child, EpisodePicked)
        assert list_view.highlighted_child.episode.title == "Alive"
