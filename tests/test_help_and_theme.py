"""Regression tests for the help screen and theme cycling.

test_help_screen_opens_without_crashing exists because HelpScreen used to
mount three Static widgets with id="help-title" and three with
id="help-body" inside the same container -- Textual widget ids must be
unique per parent, so opening it (pressing "?") raised
`MountError: Tried to insert 3 widgets with the same ID 'help-title'`
and would have crashed the whole app the first time any user pressed "?".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from torrentio_tui.config import THEMES, Config
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.ui.app import TorrentioTuiApp
from torrentio_tui.ui.screens.help import HelpScreen


@pytest.mark.asyncio
async def test_help_screen_opens_without_crashing(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.action_help()
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        app.screen.action_dismiss_help()
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_theme_cycles_through_all_curated_themes(tmp_path: Path) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        seen = [app.theme]
        for _ in range(len(THEMES)):
            app.screen.action_cycle_theme()
            await pilot.pause()
            seen.append(app.theme)

        # Every theme is a real, resolvable Textual theme (built-in or ours).
        for name in THEMES:
            assert name in app.available_themes

        # A full cycle returns to where it started.
        assert seen[0] == seen[-1]
        # And it actually visited more than one theme along the way.
        assert len(set(seen)) > 1
