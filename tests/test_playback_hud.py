from __future__ import annotations

import sys
from pathlib import Path

import pytest

from torrentio_tui.models import StreamLink
from torrentio_tui.ui.screens.playback_hud import PlaybackHudScreen
from torrentio_tui.ui.widgets.hud import StreamHud

_FAKE_MPV = Path(__file__).parent / "fixtures" / "fake_mpv.py"


def _use_fake_mpv(monkeypatch, screen_cls) -> None:
    def fake_build_command(self):
        return [
            sys.executable,
            str(_FAKE_MPV),
            f"--input-ipc-server={self._socket_path}",
        ]

    monkeypatch.setattr(screen_cls, "_build_command", fake_build_command)


@pytest.mark.asyncio
async def test_hud_screen_connects_and_polls_stats(monkeypatch):
    from textual.app import App

    _use_fake_mpv(monkeypatch, PlaybackHudScreen)

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.hud_screen = PlaybackHudScreen(
                StreamLink(url="https://example.com/a.mp4", quality="1080p"),
                "Test Movie",
                hwdec="",
            )
            self.push_screen(self.hud_screen)

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.hud_screen
        assert isinstance(screen, PlaybackHudScreen)

        # Give the fake mpv a moment to bind its socket and the screen's
        # poll timer a tick to read from it.
        for _ in range(20):
            await pilot.pause(0.1)
            if screen._ipc is not None:
                break
        assert screen._ipc is not None, "HUD never connected to the fake mpv IPC socket"

        for _ in range(10):
            await pilot.pause(0.1)

        hud = screen.query_one(StreamHud)
        assert hud._speed_samples, "HUD never recorded a cache-speed sample from IPC polling"

        screen.action_stop()
        await pilot.pause()

        assert screen._process.poll() is not None, "fake mpv was not reaped on stop"


@pytest.mark.asyncio
async def test_hud_screen_reports_spawn_error_for_missing_binary(monkeypatch):
    from textual.app import App

    def fake_build_command(self):
        return ["/nonexistent/definitely-not-mpv"]

    monkeypatch.setattr(PlaybackHudScreen, "_build_command", fake_build_command)

    class _HarnessApp(App):
        def on_mount(self) -> None:
            self.hud_screen = PlaybackHudScreen(
                StreamLink(url="https://example.com/a.mp4", quality="1080p"),
                "Test Movie",
                hwdec="",
            )
            self.push_screen(self.hud_screen)

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.hud_screen
        assert isinstance(screen, PlaybackHudScreen)
        assert isinstance(screen.spawn_error, OSError)
