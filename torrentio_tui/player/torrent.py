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


def _diagnose_streamer_failure(streamer: str, returncode: int, stderr: str) -> str:
    tail = "\n".join(stderr.strip().splitlines()[-8:]) if stderr.strip() else ""
    if "node_datachannel" in stderr or "node-datachannel" in stderr:
        return (
            f"{streamer} crashed on startup — its WebRTC native module "
            "(node-datachannel) failed to load, usually because its prebuilt "
            "binary doesn't match your installed Node.js version. Try: "
            f"`npm rebuild -g {streamer}`, a clean reinstall "
            f"(`npm uninstall -g {streamer} && npm install -g {streamer}`), "
            "switching to `peerflix` instead (`npm install -g peerflix` — no "
            "native WebRTC dependency), or configuring a debrid key in your "
            "stream addon so it returns direct http links and skips magnets "
            f"entirely.\n\n{tail}"
        )
    return f"{streamer} exited with an error (code {returncode}).\n\n{tail}"


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

    # Capture stderr only (stdout stays live so webtorrent/peerflix's own
    # progress UI still shows) so a crash — like node-datachannel's native
    # module failing to load — can be diagnosed and surfaced instead of
    # silently returning a non-zero exit code that the caller never checked.
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise TorrentStreamError(
            _diagnose_streamer_failure(streamer, result.returncode, result.stderr or "")
        )
    return result.returncode
