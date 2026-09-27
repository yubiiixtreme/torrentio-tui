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
from textual.app import SuspendNotSupported

from torrentio_tui.config import Config
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.player.torrent import TorrentStreamError
from torrentio_tui.sources.base import Source
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
        await screen.play_stream(item, episode, stream)

        assert record["resumed"] is True, (
            "player.play()'s exception escaped the suspend() block instead of "
            "being caught inside it — this reproduces the terminal-stuck-blank bug"
        )
        assert record["exc"] is None


@pytest.mark.asyncio
async def test_play_stream_handles_suspend_not_supported(tmp_path):
    """Reproduces an actual observed failure: in a headless/test driver (and
    potentially other terminal environments), App.suspend() itself raises
    SuspendNotSupported from its __enter__, before player.play() ever runs.
    That exception previously wasn't caught anywhere in play_stream(),
    killing the worker silently -- click a title, nothing happens, no error.
    """
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        item = SearchResult(id="x", title="Test Movie", kind=MediaKind.MOVIE, source_id="local")
        episode = Episode(id="x", title="Test Movie")
        stream = StreamLink(url="https://example.com/a.mp4", quality="1080p")

        # The real headless test driver already raises SuspendNotSupported
        # here (confirmed manually), but assert on it explicitly so this
        # test doesn't silently stop testing anything if that ever changes.
        with pytest.raises(SuspendNotSupported), app.suspend():
            pass

        # Must not raise, and must leave a visible error behind.
        await screen.play_stream(item, episode, stream)

        overview = screen.query_one("#detail-overview")
        assert "doesn't support suspending" in str(overview.content)


class _BrokenSource(Source):
    """A source whose get_streams() raises something other than the
    SourceError the old code only knew how to handle."""

    id = "broken"
    name = "Broken"

    def search(self, query):
        return []

    def get_streams(self, item, episode):
        raise RuntimeError("boom: unexpected bug in this source")


@pytest.mark.asyncio
async def test_open_item_surfaces_unexpected_exceptions(tmp_path):
    """open_item() must never let an unanticipated exception (not just
    SourceError) kill the worker silently -- that's exactly "click a title,
    nothing happens" from the user's side.
    """
    app = TorrentioTuiApp([_BrokenSource()], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        item = SearchResult(id="x", title="Broken Movie", kind=MediaKind.MOVIE, source_id="broken")
        screen.open_item(item)  # must not raise, even once the worker runs
        await app.workers.wait_for_complete()
        await pilot.pause()

        overview = screen.query_one("#detail-overview")
        assert "boom" in str(overview.content) or "RuntimeError" in str(overview.content)


@pytest.mark.asyncio
async def test_open_item_reports_unresolvable_source(tmp_path):
    """If item.source_id doesn't match any loaded source, the old code
    just `return`ed with zero feedback -- also "click, nothing happens"."""
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen

        item = SearchResult(id="x", title="Orphaned", kind=MediaKind.MOVIE, source_id="not-loaded")
        screen.open_item(item)
        await app.workers.wait_for_complete()
        await pilot.pause()

        overview = screen.query_one("#detail-overview")
        assert "not-loaded" in str(overview.content)


def test_stremio_source_instances_get_distinct_ids():
    """Regression: multiple config entries (stremio, mediafusion,
    knightcrawler, ...) all instantiate StremioSource. Without an explicit
    per-instance id, every instance reported the class-level "stremio" id,
    so _find_source() always resolved to whichever loaded first regardless
    of which one actually produced the clicked search result.
    """
    from torrentio_tui.sources.stremio import StremioSource

    default = StremioSource()
    mediafusion = StremioSource(
        stream_url="https://mediafusion.elfhosted.com", source_id="mediafusion"
    )

    assert default.id == "stremio"
    assert mediafusion.id == "mediafusion"
    assert default.id != mediafusion.id
