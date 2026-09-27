from __future__ import annotations

import shutil

from torrentio_tui.models import StreamLink
from torrentio_tui.player.base import Player
from torrentio_tui.player.process import run_supervised
from torrentio_tui.player.torrent import is_torrent_link, play_magnet


class VlcPlayer(Player):
    id = "vlc"

    def is_available(self) -> bool:
        return shutil.which("vlc") is not None

    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        if is_torrent_link(stream.url):
            return play_magnet(stream.url, title, backend="vlc")

        cmd = ["vlc", "--play-and-exit", f"--meta-title={title}"]

        if resume_seconds > 0:
            cmd.append(f"--start-time={resume_seconds}")

        for key, value in stream.headers.items():
            if key.lower() == "referer":
                cmd.append(f"--http-referrer={value}")
            elif key.lower() == "user-agent":
                cmd.append(f"--http-user-agent={value}")

        if stream.subtitle_url:
            cmd.append(f"--sub-file={stream.subtitle_url}")

        cmd.append(stream.url)

        result = run_supervised(cmd)
        return result.returncode
