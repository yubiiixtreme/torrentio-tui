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
            lowered = key.lower()
            if lowered == "referer":
                cmd.append(f"--http-referrer={value}")
            elif lowered == "user-agent":
                cmd.append(f"--http-user-agent={value}")
            else:
                # vlc has no per-header flags beyond referrer/user-agent;
                # --http-header forwards the rest (e.g. Authorization,
                # Cookie) instead of silently dropping them.
                cmd.append(f"--http-header={key}: {value}")

        if stream.subtitle_url:
            cmd.append(f"--sub-file={stream.subtitle_url}")

        # Buffer a few seconds up front on on-demand HTTP so playback
        # starts from the current buffer immediately and seeking to any
        # timestamp works without pre-loading the whole file. Skipped
        # for live streams (nothing to seek) and non-HTTP URLs.
        url = stream.url.lower()
        if not stream.is_live and url.startswith(("http://", "https://")):
            cmd.append("--network-caching=3000")

        cmd.append(stream.url)

        result = run_supervised(cmd)
        return result.returncode
