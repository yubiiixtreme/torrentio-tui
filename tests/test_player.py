import subprocess

import pytest

from torrentio_tui.models import StreamLink
from torrentio_tui.player.mpv import MpvPlayer
from torrentio_tui.player.registry import available_player_ids, get_player
from torrentio_tui.player.torrent import TorrentStreamError
from torrentio_tui.player.vlc_android import _VLC_ACTIVITY, VlcAndroidPlayer


def test_registry_lists_all_backends():
    ids = available_player_ids()
    assert {"mpv", "vlc", "termux", "vlc-android"} <= set(ids)


def test_get_player_threads_hwdec_only_to_mpv():
    mpv = get_player("mpv", hwdec="auto")
    assert isinstance(mpv, MpvPlayer)
    assert mpv.hwdec == "auto"

    vlc = get_player("vlc", hwdec="auto")
    assert not hasattr(vlc, "hwdec")


def test_mpv_adds_hwdec_flag(monkeypatch):
    captured = {}

    def fake_run(cmd):
        captured["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    player = MpvPlayer(hwdec="auto-safe")
    player.play(StreamLink(url="https://example.com/a.mp4", quality="1080p"), "Title")
    assert "--hwdec=auto-safe" in captured["cmd"]


def test_mpv_omits_hwdec_flag_when_empty(monkeypatch):
    captured = {}

    def fake_run(cmd):
        captured["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    player = MpvPlayer(hwdec="")
    player.play(StreamLink(url="https://example.com/a.mp4", quality="1080p"), "Title")
    assert not any(c.startswith("--hwdec") for c in captured["cmd"])


def test_vlc_android_unavailable_without_am(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    player = VlcAndroidPlayer()
    assert player.is_available() is False
    with pytest.raises(TorrentStreamError, match="am.*not found"):
        player.play(StreamLink(url="https://example.com/a.mp4", quality="1080p"), "Title")


def test_vlc_android_rejects_magnet(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "/system/bin/am")
    monkeypatch.setattr(VlcAndroidPlayer, "_vlc_installed", lambda self: True)
    player = VlcAndroidPlayer()
    magnet = StreamLink(url="magnet:?xt=urn:btih:abc123", quality="magnet")
    with pytest.raises(TorrentStreamError, match="magnet"):
        player.play(magnet, "Title")


def test_vlc_android_builds_correct_intent(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "/system/bin/am")
    monkeypatch.setattr(VlcAndroidPlayer, "_vlc_installed", lambda self: True)
    captured = {}

    def fake_run(cmd):
        captured["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    player = VlcAndroidPlayer()
    stream = StreamLink(url="https://example.com/a.mp4", quality="1080p")
    player.play(stream, "My Movie", resume_seconds=90)

    def value_after(flag: str) -> str:
        return captured["cmd"][captured["cmd"].index(flag) + 1]

    assert captured["cmd"][0] == "am"
    assert value_after("-d") == stream.url
    assert value_after("-n") == _VLC_ACTIVITY
    assert value_after("-e") == "title"
    assert value_after("--el") == "position"
    assert value_after("position") == "90000"
