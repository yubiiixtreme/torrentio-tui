from __future__ import annotations

import argparse
import shutil
import sys

from torrentio_tui.config import Config, config_file, ensure_dirs
from torrentio_tui.sources.registry import available_source_ids, load_sources
from torrentio_tui.termux import is_termux


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="torrentio-tui", description="Terminal UI for streaming from pluggable sources"
    )
    parser.add_argument(
        "--player", choices=["mpv", "vlc", "termux"], help="Override configured player backend"
    )
    parser.add_argument(
        "--list-sources", action="store_true", help="List registered source ids and exit"
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check that playback/download tools are installed and print the config path",
    )
    parser.add_argument("--version", action="store_true", help="Print the version and exit")
    return parser


def _check(label: str, ok: bool, hint: str = "") -> None:
    mark = "✓" if ok else "✗"
    line = f"  {mark} {label}"
    if not ok and hint:
        line += f"  — {hint}"
    sys.stdout.write(line + "\n")


def run_doctor() -> int:
    ensure_dirs()
    env = "Termux" if is_termux() else sys.platform
    sys.stdout.write(f"torrentio-tui — environment check ({env})\n")
    sys.stdout.write(f"Config file: {config_file()}\n\n")
    _check("mpv", shutil.which("mpv") is not None, "pkg/apt/brew install mpv")
    _check("vlc", shutil.which("vlc") is not None, "optional alternative to mpv")
    if is_termux():
        _check(
            "termux-open (termux-api)",
            shutil.which("termux-open") is not None,
            "pkg install termux-api, then install the Termux:API app",
        )
    _check(
        "yt-dlp", shutil.which("yt-dlp") is not None, "pip install yt-dlp — needed for downloads"
    )
    _check(
        "webtorrent or peerflix",
        shutil.which("webtorrent") is not None or shutil.which("peerflix") is not None,
        "npm install -g webtorrent-cli — only needed for magnet streams without a debrid key",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        from torrentio_tui import __version__

        sys.stdout.write(__version__ + "\n")
        return 0

    if args.list_sources:
        out = sys.stdout
        for source_id in available_source_ids():
            out.write(source_id + "\n")
        return 0

    if args.doctor:
        return run_doctor()

    ensure_dirs()
    config = Config.load()
    if args.player:
        config.player.backend = args.player

    sources = load_sources(
        config.enabled_sources,
        stremio_cinemeta_url=config.stremio.cinemeta_url,
        stremio_stream_url=config.stremio.stream_url,
        stremio_timeout=config.stremio.timeout_seconds,
    )
    if not sources:
        sys.stderr.write("No sources enabled. Edit sources.enabled in your config file.\n")
        return 1

    from torrentio_tui.ui.app import TorrentioTuiApp

    app = TorrentioTuiApp(sources, config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
