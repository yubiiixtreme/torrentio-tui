"""Playback on Android by launching VLC directly via an `am start` intent.

`termux.py` hands the URL to `termux-open`, which lets Android pick
whatever app is registered for the content type (sometimes prompting an
app-chooser dialog, and dropping the resume position since generic
ACTION_VIEW has no notion of it). This backend instead targets VLC for
Android's player activity directly, per VLC's own documented Android
intent API (https://wiki.videolan.org/Android_Player_Intents/):

    am start -a android.intent.action.VIEW -d "<url>" -t video/* \\
        -n org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity \\
        -e title "<title>" --el position <resume_ms>

`am` (Android's activity manager) is available in Termux out of the box —
no `termux-api` package needed for this one, just VLC for Android
installed (F-Droid or Play Store).

Like the generic `termux` backend, `am start` only dispatches the intent
and returns immediately — it does not block until VLC exits, and can't
play magnet/torrent links without a torrent-capable app registered as a
magnet handler.
"""

from __future__ import annotations

import shutil
import subprocess

from torrentio_tui.models import StreamLink
from torrentio_tui.player.base import Player
from torrentio_tui.player.torrent import TorrentStreamError, is_torrent_link

_VLC_ACTIVITY = "org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity"
_VLC_PACKAGE = "org.videolan.vlc"


class VlcAndroidPlayer(Player):
    id = "vlc-android"

    def _vlc_installed(self) -> bool:
        try:
            result = subprocess.run(
                ["pm", "list", "packages", _VLC_PACKAGE],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return _VLC_PACKAGE in result.stdout

    def is_available(self) -> bool:
        return shutil.which("am") is not None and self._vlc_installed()

    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        if shutil.which("am") is None:
            raise TorrentStreamError(
                "`am` (Android activity manager) not found — this backend only works "
                "inside Termux on Android."
            )
        if not self._vlc_installed():
            raise TorrentStreamError(
                "VLC for Android isn't installed. Install it from F-Droid or the Play "
                "Store, or use the `termux` backend instead to pick any installed player."
            )
        if is_torrent_link(stream.url):
            raise TorrentStreamError(
                "This is a magnet/torrent stream — VLC for Android can't open those "
                "directly. Configure a debrid key in your stream addon so it returns "
                "direct http(s) links instead, or install a torrent app that registers "
                "as a magnet handler on this device."
            )

        cmd = [
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            stream.url,
            "-t",
            "video/*",
            "-n",
            _VLC_ACTIVITY,
            "-e",
            "title",
            title,
        ]
        if resume_seconds > 0:
            cmd += ["--el", "position", str(int(resume_seconds * 1000))]

        result = subprocess.run(cmd)
        return result.returncode
