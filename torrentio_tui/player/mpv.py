from __future__ import annotations

import shutil

from torrentio_tui.models import StreamLink
from torrentio_tui.player.base import Player
from torrentio_tui.player.process import run_supervised
from torrentio_tui.player.torrent import is_torrent_link, play_magnet


def mpv_language_args() -> list[str]:
    """`--slang/--alang` from the user's preferred languages, so mpv
    auto-selects matching audio/subtitle tracks. Best-effort: any config
    problem means "no flags" rather than broken playback."""
    try:
        from torrentio_tui.config import get_language_config
        from torrentio_tui.languages import SUBTITLE_LANGUAGE_CODES

        prefs = get_language_config()
    except Exception:
        return []
    to_639_1 = {code: lang.value for code, lang in SUBTITLE_LANGUAGE_CODES.items()}

    def map_codes(codes: list[str]) -> list[str]:
        seen: list[str] = []
        for code in codes:
            mapped = to_639_1.get(code, code)
            if mapped not in seen:
                seen.append(mapped)
        return seen

    args = []
    slang = map_codes(list(prefs.subtitle_languages))
    if slang:
        args.append(f"--slang={','.join(slang)}")
    alang = map_codes(list(prefs.audio_languages))
    if alang:
        args.append(f"--alang={','.join(alang)}")
    return args


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

        cmd.extend(mpv_language_args())

        cmd.append(stream.url)

        result = run_supervised(cmd)
        return result.returncode
