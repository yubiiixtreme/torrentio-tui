"""Batch downloading, following ani-cli's approach of shelling out to
yt-dlp (handles HLS/m3u8, resumes, range requests) rather than
reimplementing an HTTP downloader.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from stream_tui.models import StreamLink
from stream_tui.player.torrent import is_torrent_link


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
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip() or "video"
    output_template = str(dest_dir / f"{safe_title}.%(ext)s")

    cmd = ["yt-dlp", "--continue", "--no-part", "-o", output_template]

    for key, value in stream.headers.items():
        cmd += ["--add-header", f"{key}:{value}"]

    cmd.append(stream.url)

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert process.stdout is not None
    for line in process.stdout:
        if on_output:
            on_output(line.rstrip())

    returncode = process.wait()
    if returncode != 0:
        raise DownloadError(f"yt-dlp exited with code {returncode}")

    return dest_dir
