from __future__ import annotations

import argparse
import sys

from stream_tui.config import Config, ensure_dirs
from stream_tui.sources.registry import available_source_ids, load_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stream-tui", description="Terminal UI for streaming from pluggable sources")
    parser.add_argument("--player", choices=["mpv", "vlc"], help="Override configured player backend")
    parser.add_argument("--list-sources", action="store_true", help="List registered source ids and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_sources:
        for source_id in available_source_ids():
            print(source_id)
        return 0

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
        print("No sources enabled. Edit sources.enabled in your config file.", file=sys.stderr)
        return 1

    from stream_tui.ui.app import StreamTuiApp

    app = StreamTuiApp(sources, config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
