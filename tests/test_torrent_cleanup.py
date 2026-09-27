"""Regression coverage for a real disk-hygiene gap: webtorrent-cli and
peerflix both buffer downloaded torrent pieces to disk somewhere (a
shared OS temp folder by default) while streaming a magnet. Left alone,
that data isn't guaranteed to be cleaned up -- webtorrent-cli has no
auto-remove flag at all, and peerflix's own `--remove` only fires from
a signal handler, so an unclean exit could skip it. play_magnet() now
points both tools at a directory it owns and always removes it itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from torrentio_tui.player import torrent as torrent_mod


class _FakeResult:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def test_peerflix_gets_a_private_buffer_dir_and_auto_remove(monkeypatch) -> None:
    monkeypatch.setattr(
        torrent_mod.shutil, "which", lambda name: name if name == "peerflix" else None
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["dir_existed_during_call"] = Path(cmd[cmd.index("--path") + 1]).is_dir()
        return _FakeResult()

    monkeypatch.setattr(torrent_mod, "run_supervised", fake_run)
    torrent_mod.play_magnet("magnet:?xt=urn:btih:abc", "T", backend="mpv")

    cmd = captured["cmd"]
    assert "--remove" in cmd
    buffer_dir = cmd[cmd.index("--path") + 1]
    assert "torrentio-tui-torrent-" in buffer_dir
    assert captured["dir_existed_during_call"], "buffer dir must exist while the streamer runs"
    assert not Path(buffer_dir).exists(), "buffer dir must be gone once play_magnet returns"


def test_webtorrent_gets_a_private_out_dir_that_is_removed_after(monkeypatch) -> None:
    monkeypatch.setattr(
        torrent_mod.shutil, "which", lambda name: name if name == "webtorrent" else None
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["dir_existed_during_call"] = Path(cmd[cmd.index("--out") + 1]).is_dir()
        return _FakeResult()

    monkeypatch.setattr(torrent_mod, "run_supervised", fake_run)
    torrent_mod.play_magnet("magnet:?xt=urn:btih:abc", "T", backend="mpv")

    out_dir = captured["cmd"][captured["cmd"].index("--out") + 1]
    assert "torrentio-tui-torrent-" in out_dir
    assert captured["dir_existed_during_call"]
    assert not Path(out_dir).exists()


def test_buffer_dir_is_still_removed_when_the_streamer_crashes(monkeypatch) -> None:
    """The cleanup must not depend on a clean exit -- a crash is exactly
    the case a leftover multi-gigabyte buffer directory matters most."""
    monkeypatch.setattr(
        torrent_mod.shutil, "which", lambda name: name if name == "webtorrent" else None
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["dir"] = cmd[cmd.index("--out") + 1]
        return _FakeResult(returncode=1, stderr="boom")

    monkeypatch.setattr(torrent_mod, "run_supervised", fake_run)
    with pytest.raises(torrent_mod.TorrentStreamError):
        torrent_mod.play_magnet("magnet:?xt=urn:btih:abc", "T", backend="mpv")

    assert not Path(captured["dir"]).exists()


def test_buffer_dir_removed_even_if_the_streamer_already_deleted_it(monkeypatch) -> None:
    """peerflix's own --remove may already delete the directory itself;
    our own cleanup (ignore_cleanup_errors=True) must not choke on that."""
    import shutil as shutil_mod

    monkeypatch.setattr(
        torrent_mod.shutil, "which", lambda name: name if name == "peerflix" else None
    )

    def fake_run(cmd, **kwargs):
        buffer_dir = cmd[cmd.index("--path") + 1]
        shutil_mod.rmtree(buffer_dir)  # simulate peerflix's own --remove already firing
        return _FakeResult()

    monkeypatch.setattr(torrent_mod, "run_supervised", fake_run)
    # Must not raise even though the directory is already gone.
    torrent_mod.play_magnet("magnet:?xt=urn:btih:abc", "T", backend="mpv")
