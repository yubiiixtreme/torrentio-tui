"""Playback on Termux via Android's own share/open intent.

Termux itself is headless (no video output), so instead of trying to run
mpv/vlc in the terminal, this hands the stream URL to `termux-open`, which
asks Android to open it in whatever app is registered for it — typically
the user's video player (VLC, MX Player, ...). Playback then runs outside
Termux entirely, same as ani-cli's Android handling.

Requires the `termux-api` package (`pkg install termux-api`) plus the
companion Termux:API app installed from F-Droid or Google Play.

Magnet links generally won't resolve this way unless a torrent-capable app
is registered as a magnet handler on the device — direct http(s) links
(e.g. from a debrid-unrestricted Torrentio stream) are what this is for.
"""

from __future__ import annotations

import shutil
import subprocess

from torrentio_tui.models import StreamLink
from torrentio_tui.player.base import Player
from torrentio_tui.player.torrent import TorrentStreamError, is_torrent_link


class TermuxPlayer(Player):
    id = "termux"

    def is_available(self) -> bool:
        return shutil.which("termux-open") is not None

    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        if not self.is_available():
            raise TorrentStreamError(
                "termux-open not found. Install it with `pkg install termux-api` and "
                "install the Termux:API companion app (F-Droid/Play Store), then retry."
            )
        if is_torrent_link(stream.url):
            raise TorrentStreamError(
                "This is a magnet/torrent stream — Termux can't play those directly. "
                "Configure a debrid key in your stream addon so it returns direct "
                "http(s) links instead, or install a torrent app that registers as a "
                "magnet handler on this device."
            )

        result = subprocess.run(["termux-open", "--content-type", "video/*", stream.url])
        return result.returncode
