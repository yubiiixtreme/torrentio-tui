"""Bridge from magnet/torrent links to desktop players.

mpv and vlc cannot play ``magnet:`` links natively. When a stream addon
(like Torrentio without a debrid key) returns infoHash magnets, we hand
the magnet to a local torrent streamer if one is installed:

* ``webtorrent "<magnet>" --mpv`` (webtorrent-cli, ``npm i -g webtorrent-cli``)
* ``peerflix "<magnet>" --mpv`` / ``--vlc``

Direct http(s) URLs (debrid unrestricts) play natively and never touch this.
"""

from __future__ import annotations

import shutil
import subprocess


class TorrentStreamError(Exception):
    pass


def is_torrent_link(url: str) -> bool:
    u = url.lower()
    return u.startswith("magnet:?") or u.endswith(".torrent") or "btih:" in u


def find_streamer() -> str | None:
    for binary in ("webtorrent", "peerflix"):
        if shutil.which(binary):
            return binary
    return None


def play_magnet(magnet: str, title: str, backend: str = "mpv") -> int:
    streamer = find_streamer()
    if streamer is None:
        raise TorrentStreamError(
            "This is a torrent/magnet stream, but no torrent streamer was "
            "found. Install one (`npm install -g webtorrent-cli`) or "
            "configure a debrid key in your stream addon URL so it returns "
            "direct http links. Magnet (truncated): " + magnet[:80] + "..."
        )
    if streamer == "webtorrent":
        player_flag = {"mpv": "--mpv", "vlc": "--vlc"}.get(backend, "--mpv")
        cmd = ["webtorrent", magnet, player_flag, f"--title={title}"]
    else:  # peerflix
        player_flag = {"mpv": "--mpv", "vlc": "--vlc"}.get(backend, "--mpv")
        cmd = ["peerflix", magnet, player_flag]
    result = subprocess.run(cmd)
    return result.returncode
