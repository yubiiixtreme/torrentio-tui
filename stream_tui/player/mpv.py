from __future__ import annotations

import shutil
import subprocess

from stream_tui.models import StreamLink
from stream_tui.player.base import Player
from stream_tui.player.torrent import is_torrent_link, play_magnet


class MpvPlayer(Player):
    id = "mpv"

    def is_available(self) -> bool:
        return shutil.which("mpv") is not None

    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        if is_torrent_link(stream.url):
            return play_magnet(stream.url, title, backend="mpv")

        cmd = ["mpv", f"--force-media-title={title}", "--save-position-on-quit"]

        if resume_seconds > 0:
            cmd.append(f"--start={resume_seconds}")

        if stream.headers:
            fields = ",".join(f"{key}: {value}" for key, value in stream.headers.items())
            cmd.append(f"--http-header-fields={fields}")

        if stream.subtitle_url:
            cmd.append(f"--sub-file={stream.subtitle_url}")

        cmd.append(stream.url)

        result = subprocess.run(cmd)
        return result.returncode
