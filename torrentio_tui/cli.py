from __future__ import annotations

import argparse
import shutil
import sys

from torrentio_tui.config import Config, config_file, ensure_dirs
from torrentio_tui.player.registry import available_player_ids
from torrentio_tui.sources.registry import available_source_ids, load_sources
from torrentio_tui.termux import is_termux


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="torrentio-tui", description="Terminal UI for streaming from pluggable sources"
    )
    parser.add_argument(
        "--player", choices=available_player_ids(), help="Override configured player backend"
    )
    parser.add_argument(
        "--hwdec",
        metavar="MODE",
        help="Override mpv's --hwdec mode for this run (e.g. auto-safe, auto, no)",
    )
    parser.add_argument(
        "--proxy",
        metavar="URL",
        help="Route Cinemeta/Torrentio requests through a proxy for this run "
        "(e.g. socks5://127.0.0.1:40000 for Cloudflare WARP's proxy mode)",
    )
    parser.add_argument(
        "--list-sources", action="store_true", help="List registered source ids and exit"
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check that playback/download tools are installed and print the config path",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="With --doctor, skip the live Cinemeta/Torrentio reachability check",
    )
    parser.add_argument("--version", action="store_true", help="Print the version and exit")
    return parser


def _check(label: str, ok: bool, hint: str = "") -> None:
    mark = "✓" if ok else "✗"
    line = f"  {mark} {label}"
    if not ok and hint:
        line += f"  — {hint}"
    sys.stdout.write(line + "\n")


def _check_reachable(label: str, url: str, timeout: float, proxy_url: str | None) -> None:
    import urllib.error

    from torrentio_tui.proxy import ProxyError, open_url

    try:
        with open_url(url, timeout, proxy_url, {"Accept": "application/json"}):
            pass
        _check(label, True)
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            hint = (
                "blocked (HTTP 403) even through your configured proxy — try a different one"
                if proxy_url
                else "blocked (HTTP 403) — Cloudflare is flagging this IP; set "
                "network.proxy_url or --proxy"
            )
        else:
            hint = f"HTTP {exc.code}"
        _check(label, False, hint)
    except (ProxyError, urllib.error.URLError, TimeoutError, OSError) as exc:
        _check(label, False, str(exc))


def run_doctor(proxy_override: str | None = None, offline: bool = False) -> int:
    from torrentio_tui.proxy import pysocks_available

    ensure_dirs()
    config = Config.load()
    if proxy_override:
        config.network.proxy_url = proxy_override
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
        from torrentio_tui.player.vlc_android import VlcAndroidPlayer

        _check(
            "VLC for Android (vlc-android backend)",
            VlcAndroidPlayer().is_available(),
            "install VLC from F-Droid/Play Store to use --player vlc-android",
        )
    _check(
        "yt-dlp", shutil.which("yt-dlp") is not None, "pip install yt-dlp — needed for downloads"
    )
    _check(
        "peerflix or webtorrent",
        shutil.which("peerflix") is not None or shutil.which("webtorrent") is not None,
        "npm install -g peerflix — preferred for magnet streams without a debrid key",
    )
    sys.stdout.write(f"\nPlayer backend: {config.player.backend}\n")
    sys.stdout.write(f"mpv hwdec: {config.player.hwdec or '(disabled)'}\n")
    proxy_url = config.network.proxy_url
    if proxy_url:
        sys.stdout.write(f"\nProxy configured: {proxy_url}\n")
        if proxy_url.startswith("socks"):
            _check("pysocks (for socks5:// proxy)", pysocks_available(), "pip install pysocks")
    else:
        sys.stdout.write("\nNo proxy configured.\n")

    if offline:
        sys.stdout.write("\n(--offline: skipped the live reachability check)\n")
        return 0

    sys.stdout.write("\nChecking connectivity (use --offline to skip)...\n")
    # Check Cinemeta once
    _check_reachable("Cinemeta", f"{config.stremio.cinemeta_url}/manifest.json", 8.0, proxy_url)
    # Check each enabled Stremio-like source's stream addon
    seen_stream_urls = set()
    for source_id in config.enabled_sources:
        if source_id in ("stremio", "mediafusion", "knightcrawler", "torrentio-selfhost"):
            source_cfg = config.sources_config.get(source_id, {})
            stream_url = source_cfg.get("stream_url")
            if not stream_url:
                if source_id == "mediafusion":
                    stream_url = "https://mediafusion.elfhosted.com"
                elif source_id == "knightcrawler":
                    stream_url = "https://knightcrawler.ml"
                elif source_id == "torrentio-selfhost":
                    stream_url = "http://localhost:7000"
                else:
                    stream_url = config.stremio.stream_url
            if stream_url not in seen_stream_urls:
                seen_stream_urls.add(stream_url)
                _check_reachable(
                    f"Stream addon ({source_id})", f"{stream_url}/manifest.json", 8.0, proxy_url
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
        return run_doctor(args.proxy, args.offline)

    ensure_dirs()
    config = Config.load()
    if args.player:
        config.player.backend = args.player
    if args.hwdec is not None:
        config.player.hwdec = args.hwdec
    if args.proxy:
        config.network.proxy_url = args.proxy

    sources = load_sources(config)
    if not sources:
        sys.stderr.write("No sources enabled. Edit sources.enabled in your config file.\n")
        return 1

    from torrentio_tui.ui.app import TorrentioTuiApp

    app = TorrentioTuiApp(sources, config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
