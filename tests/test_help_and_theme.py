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
        # Use the action name directly since key bindings might not work in test env
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


@pytest.mark.asyncio
async def test_unknown_configured_theme_warns_instead_of_silently_swapping(
    tmp_path: Path,
) -> None:
    """A name in config.toml that isn't a real theme must be surfaced.

    The old code fell back to "torrentio" with no output, which is
    indistinguishable from "the theme never persists" -- the symptom
    that sent us looking here in the first place.
    """
    config = Config()
    config.ui.theme = "midnight"  # not a Textual builtin, not one of ours
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], config)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme == "torrentio"  # still falls back, so the app runs
        notifications = [str(n.message) for n in app._notifications]
        assert any("midnight" in msg for msg in notifications), (
            f"unknown theme was swapped silently; notifications={notifications}"
        )


@pytest.mark.asyncio
async def test_known_configured_theme_is_applied_without_warning(tmp_path: Path) -> None:
    config = Config()
    config.ui.theme = "nord"
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], config)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme == "nord"
        assert not app._notifications
