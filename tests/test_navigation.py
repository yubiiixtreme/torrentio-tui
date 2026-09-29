from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, ListItem, ListView, Static

from torrentio_tui.config import Config
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.ui.app import TorrentioTuiApp
from torrentio_tui.ui.widgets import VimListView


@pytest.mark.asyncio
async def test_vim_list_view_j_k_move_cursor_like_arrows() -> None:
    from textual.app import App

    class _HarnessApp(App):
        def compose(self):
            yield VimListView(
                ListItem(Static("one")), ListItem(Static("two")), ListItem(Static("three"))
            )

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        list_view = app.query_one(VimListView)
        list_view.focus()
        assert list_view.index == 0

        await pilot.press("j")
        assert list_view.index == 1

        await pilot.press("j")
        assert list_view.index == 2

        await pilot.press("k")
        assert list_view.index == 1


@pytest.mark.asyncio
async def test_slash_focuses_search_and_selects_existing_text(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        search_input = screen.query_one("#search-input", Input)
        search_input.value = "old query"

        # Switch away from the search view first, so "/" has to jump back.
        screen._show_view("continue")
        await pilot.pause()
        assert screen.query_one("#view-search").display is False

        screen.action_focus_search()
        await pilot.pause()

        assert screen.query_one("#view-search").display is not False
        assert search_input.has_focus
        assert search_input.selected_text == "old query"


@pytest.mark.asyncio
async def test_search_results_list_view_is_vim_navigable(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        results_list = app.screen.query_one("#search-results", ListView)
        assert isinstance(results_list, VimListView)


@pytest.mark.asyncio
async def test_sidebar_switches_views(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        # App opens alive on trending.
        assert screen._active_view == "trending"
        assert screen.query_one("#view-trending").display is not False

        screen._show_view("sources")
        await pilot.pause()
        assert screen._active_view == "sources"
        assert screen.query_one("#view-sources").display is not False
        assert screen.query_one("#view-trending").display is False
        assert screen.query_one("#nav-sources", Button).variant == "primary"

        # Number keys jump sections.
        await pilot.press("1")
        await pilot.pause()
        assert screen._active_view == "search"


@pytest.mark.asyncio
async def test_sidebar_shows_source_counts(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        status = str(app.screen.query_one("#sidebar-status").render())
        assert "sources on" in status
