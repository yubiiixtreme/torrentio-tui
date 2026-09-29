from __future__ import annotations

import pytest

from torrentio_tui.models import Episode
from torrentio_tui.ui.screens.episodes import EpisodePicked, EpisodeScreen, SeasonHeader


def _episode(season: int | None, number: int | None, title: str) -> Episode:
    return Episode(id=f"{season}-{number}-{title}", title=title, season=season, number=number)


@pytest.mark.asyncio
async def test_multi_season_list_gets_a_header_per_season(tmp_path) -> None:
    from textual.app import App

    episodes = [
        _episode(1, 1, "Pilot"),
        _episode(1, 2, "Cool Off"),
        _episode(2, 1, "It's Alive!"),
    ]

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.push_screen(EpisodeScreen(episodes))

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, EpisodeScreen)

        headers = list(screen.query(SeasonHeader))
        picks = list(screen.query(EpisodePicked))
        assert len(headers) == 2
        assert len(picks) == 3
        assert all(row.disabled for row in headers)
        assert not any(row.disabled for row in picks)


@pytest.mark.asyncio
async def test_single_season_list_has_no_header(tmp_path) -> None:
    from textual.app import App

    episodes = [_episode(1, 1, "Pilot"), _episode(1, 2, "Cool Off")]

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.push_screen(EpisodeScreen(episodes))

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert list(screen.query(SeasonHeader)) == []
        assert len(list(screen.query(EpisodePicked))) == 2


@pytest.mark.asyncio
async def test_initial_highlight_skips_the_season_header(tmp_path) -> None:
    from textual.app import App
    from textual.widgets import ListView

    episodes = [_episode(1, 1, "Pilot"), _episode(2, 1, "It's Alive!")]

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.push_screen(EpisodeScreen(episodes))

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        list_view = screen.query_one(ListView)
        assert isinstance(list_view.highlighted_child, EpisodePicked)
        assert list_view.highlighted_child.episode.title == "Pilot"


@pytest.mark.asyncio
async def test_cursor_down_skips_over_season_header(tmp_path) -> None:
    from textual.app import App
    from textual.widgets import ListView

    episodes = [
        _episode(1, 1, "Pilot"),
        _episode(2, 1, "It's Alive!"),
        _episode(2, 2, "Popping Cherry"),
    ]

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.push_screen(EpisodeScreen(episodes))

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        list_view = app.screen.query_one(ListView)
        list_view.focus()

        await pilot.press("j")  # Pilot -> should land on "It's Alive!", skipping "Season 2" header
        assert isinstance(list_view.highlighted_child, EpisodePicked)
        assert list_view.highlighted_child.episode.title == "It's Alive!"
