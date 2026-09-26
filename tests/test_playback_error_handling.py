"""Regression test for a real bug: Textual's `App.suspend()` only resumes
the terminal driver if the code inside its `with` block returns normally
(its implementation has no try/finally around the internal `yield`). If
`player.play()` raises inside that block — e.g. a magnet link with no
`webtorrent`/`peerflix` installed — the terminal was left stuck in
suspended raw mode: blank screen, no redraw, effectively dead, even
though the app itself kept running.

The fix is that `MainScreen.play_stream()` must catch player errors
*inside* `with self.app.suspend():`, not around it, so `suspend()`
always completes its normal resume path first.
"""

from __future__ import annotations

import contextlib

import pytest

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.player.torrent import TorrentStreamError
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.ui.app import TorrentioTuiApp


class _RaisingPlayer:
    """Stands in for any player backend failing the way a magnet stream
    does with no torrent streamer installed."""

    def play(self, stream, title, resume_seconds=0.0):
        raise TorrentStreamError("no torrent streamer installed")

    def is_available(self):
        return True


@contextlib.contextmanager
def _fake_suspend_like_textual(record: dict):
    """Mirrors the *actual* shape of Textual's App.suspend(): whatever
    happens inside the `with` block is only followed by "resume" work if
    the block exits without raising."""
    try:
        yield
    except BaseException as exc:
        record["resumed"] = False
        record["exc"] = exc
        raise
    else:
        record["resumed"] = True
        record["exc"] = None


@pytest.mark.asyncio
async def test_play_stream_resumes_terminal_even_when_player_raises(monkeypatch, tmp_path):
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        monkeypatch.setattr(
            "torrentio_tui.ui.screens.main.get_player",
            lambda backend, hwdec="": _RaisingPlayer(),
        )

        record: dict = {"resumed": None, "exc": None}
        monkeypatch.setattr(app, "suspend", lambda: _fake_suspend_like_textual(record))

        item = SearchResult(id="x", title="Test Movie", kind=MediaKind.MOVIE, source_id="local")
        episode = Episode(id="x", title="Test Movie")
        stream = StreamLink(url="magnet:?xt=urn:btih:abc123", quality="magnet")

        # Must not raise — and must not leave suspend()'s block via exception.
        screen.play_stream(item, episode, stream)

        assert record["resumed"] is True, (
            "player.play()'s exception escaped the suspend() block instead of "
            "being caught inside it — this reproduces the terminal-stuck-blank bug"
        )
        assert record["exc"] is None
