from __future__ import annotations

import shutil

from torrentio_tui.models import StreamLink
from torrentio_tui.player.base import Player
from torrentio_tui.player.process import run_supervised
from torrentio_tui.player.torrent import is_torrent_link, play_magnet


class MpvPlayer(Player):
    id = "mpv"

    def __init__(self, hwdec: str = "") -> None:
        self.hwdec = hwdec

    def is_available(self) -> bool:
        return shutil.which("mpv") is not None

    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        if is_torrent_link(stream.url):
            return play_magnet(stream.url, title, backend="mpv")

        cmd = ["mpv", f"--force-media-title={title}", "--save-position-on-quit"]

        if self.hwdec:
            cmd.append(f"--hwdec={self.hwdec}")

        if resume_seconds > 0:
            cmd.append(f"--start={resume_seconds}")

        if stream.headers:
            fields = ",".join(f"{key}: {value}" for key, value in stream.headers.items())
            cmd.append(f"--http-header-fields={fields}")

        if stream.subtitle_url:
            cmd.append(f"--sub-file={stream.subtitle_url}")

        cmd.append(stream.url)

        result = run_supervised(cmd)
        return result.returncode
