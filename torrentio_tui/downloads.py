"""Batch downloading, following ani-cli's approach of shelling out to
yt-dlp (handles HLS/m3u8, resumes, range requests) rather than
reimplementing an HTTP downloader.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from torrentio_tui.models import StreamLink
from torrentio_tui.player.process import supervised_popen
from torrentio_tui.player.torrent import is_torrent_link


class DownloadError(Exception):
    pass


def is_available() -> bool:
    return shutil.which("yt-dlp") is not None


def download(
    stream: StreamLink,
    title: str,
    dest_dir: Path,
    on_output: Callable[[str], None] | None = None,
) -> Path:
    if is_torrent_link(stream.url):
        raise DownloadError(
            "This is a torrent/magnet stream — yt-dlp can't download it. "
            "Use a torrent client, or configure a debrid key so the addon "
            "returns direct http links."
        )
    if not is_available():
        raise DownloadError("yt-dlp is not installed or not on PATH")

    dest_dir.mkdir(parents=True, exist_ok=True)
    # Keep unicode letters (CJK/anime titles) — the old
    # `c.isalnum()`-with-ASCII-assumption stripped them entirely, so
    # distinct titles collapsed to "video.%(ext)s" and overwrote each
    # other. Only strip what filesystems actually dislike.
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip().rstrip(".") or "video"
    output_template = str(dest_dir / f"{safe_title}.%(ext)s")

    cmd = ["yt-dlp", "--continue", "--no-part", "-o", output_template]

    for key, value in stream.headers.items():
        cmd += ["--add-header", f"{key}: {value}"]

    cmd.append(stream.url)

    with supervised_popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as process:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                if on_output:
                    on_output(line.rstrip())
        finally:
            # Release the pipe promptly instead of leaving it for the GC
            # (previously surfaced as ResourceWarning: unclosed file).
            # Guarded: test doubles may substitute a plain iterator.
            close = getattr(process.stdout, "close", None)
            if callable(close):
                close()
        returncode = process.wait()

    if returncode != 0:
        raise DownloadError(f"yt-dlp exited with code {returncode}")

    return dest_dir
