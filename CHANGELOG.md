# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-09-26

### Fixed
- **Magnet streaming now works** — Fixed torrent streamer preference to use `peerflix` (more reliable) over `webtorrent` (has Node.js native module issues on newer Node versions). Install with `npm install -g peerflix`.
- **Torrentio Cloudflare 403 workaround** — MediaFusion now works when configured at https://mediafusion.elfhosted.com/configure (add your debrid services and providers).
- **Doctor command** — Now recommends `peerflix` as preferred torrent streamer.

### Added
- **Peerflix preference** — `find_streamer()` now checks for `peerflix` first, falls back to `webtorrent`.
- **MediaFusion configuration docs** — Added notes about configuring MediaFusion for debrid links.
- **Tests** — New tests for torrent streamer selection logic.

### Changed
- Updated help screen and doctor output to recommend `peerflix`.
- Default config.toml now has `mediafusion` enabled by default.

## [0.5.0] - 2026-09-26

## [0.4.0] - 2026-09-26

### Added
- **Alternative stream addons** — MediaFusion (`mediafusion`), Knightcrawler (`knightcrawler`), and self-hosted Torrentio (`torrentio-selfhost`) as drop-in replacements for the default Torrentio stream source. MediaFusion works without proxy and often returns direct debrid links.
- **IPTV/Live TV source** (`iptv`) — Load live TV channels from M3U playlists (URL or local file). Configure via `[sources.iptv]` with `m3u_url` or `m3u_path`.
- **Anime-specific sources** — AniList (`anilist`, GraphQL API for rich metadata), Nyaa.si (`nyaa`, anime torrents), SubsPlease (`subsplease`, latest simulcast releases).
- **Adult content sources** (opt-in) — Stremio Adult (`stremio-adult`) and Hanime.tv (`hanime`). Requires `[adult] enabled = true` in config.toml.
- **Improved proxy support** — Doctor command now checks all enabled stream addons; better SOCKS5 proxy handling with PySocks.
- **Cozy UI theme** — Warmer color palette (slate-950 background, gold primary, purple secondary, rose accent), larger modals, better scrollbars, toast notifications.
- **Enhanced help screen** — Now includes source listing with descriptions, usage tips, and troubleshooting hints.
- **Source badges in search results** — Color-coded source identifiers (yellow=stremio, green=mediafusion, red=iptv, cyan=anilist, etc.).
- **Environment variable for adult content** — `TORRENTIO_TUI_ADULT=1` to enable adult sources without editing config.
- **Config sections for IPTV and adult** — `[sources.iptv]`, `[sources.anilist]`, `[sources.nyaa]`, `[sources.subsplease]`, `[sources.stremio-adult]`, `[sources.hanime]`, `[adult]`.

### Fixed
- **Torrentio Cloudflare 403 workaround** — By adding MediaFusion as default alternative, most users can now stream without needing a proxy. Torrentio still works with proxy for those who prefer it.
- **Doctor command** — Now reports connectivity for all enabled Stremio-like sources, not just the first one.
- **Library refresh crash** — Fixed `NameError` when refreshing library with results from new sources.

### Changed
- Default config.toml now includes commented examples for all new sources.
- Theme colors updated for better readability and "coziness".
- Help screen (`?`) is now a comprehensive reference with keybindings, sources, and tips.

## [0.3.0] - 2026-09-26

### Fixed
- **Python 3.10 was completely broken** — `config.py` imported stdlib
  `tomllib` unconditionally, but that module only exists from Python 3.11
  onward, despite `pyproject.toml` claiming `requires-python = ">=3.10"`.
  Any real 3.10 install would crash on the very first import. Caught by
  CI's 3.10 job failing; now falls back to the `tomli` backport (added as
  a conditional dependency for `python_version < "3.11"`) on 3.10.
- Removed the PyPI badges from the README — they showed "package/version
  not found" because nothing has actually been published to PyPI or
  tagged as a GitHub release yet, not because they were broken. Replaced
  with a static Python-version badge; can bring the PyPI ones back once
  there's an actual release to point them at.

### Added
- **`vlc-android` player backend** — launches VLC for Android directly via
  an `am start` intent (per VLC's documented Android intent API) instead
  of the generic `termux` backend's app-chooser hand-off, and carries the
  resume position across. `--doctor` checks whether VLC for Android is
  installed when run inside Termux.
- **mpv hardware decoding** (`player.hwdec` / `TORRENTIO_TUI_HWDEC` /
  `--hwdec`) — defaults to mpv's own recommended `auto-safe` mode
  everywhere; most impactful on Android but harmless on desktop.
- **Outbound proxy support** (`network.proxy_url` / `TORRENTIO_TUI_PROXY` /
  `--proxy`) for Cinemeta and Torrentio requests — `http://`/`https://`
  proxies work out of the box, `socks5://` needs the optional `pysocks`
  dependency (`torrentio-tui[proxy]`). Documented against Cloudflare WARP's
  local proxy mode, for when Torrentio's Cloudflare 403 hits an IP that
  the official Stremio app on the same machine doesn't trigger it on.
  `--doctor` reports whether a proxy is configured and whether PySocks is
  installed.
- **`--doctor` live reachability probe** — actually fetches Cinemeta's and
  the configured stream addon's manifest (through the configured proxy, if
  any) and reports success / HTTP 403 / network error, so a blocked IP
  shows up before you try to search. `--offline` skips it.
- **Termux (Android) support** — a `termux` player backend that hands the
  stream URL to Android via `termux-open` instead of trying to run mpv in
  the (headless) terminal; auto-selected as the default backend when
  running inside Termux
- **`--doctor`** — checks mpv/vlc/yt-dlp/webtorrent/termux-open and prints
  the active config file path
- **`--version`**
- **In-app help (`?`)** — keybindings cheat sheet as a modal
- **Real `d` (download)** — downloads the highlighted result via `yt-dlp`,
  with quality picker and progress notifications (was previously a stub)
- **Genres** in the detail panel and `i` info popup, sourced from Cinemeta
- **Stream type badges** — DIRECT, DEBRID, MAGNET indicators in the quality
  picker
- Ruff linting + formatting config, CONTRIBUTING.md, CODE_OF_CONDUCT.md

### Fixed
- **Terminal left dead after a failed magnet playback attempt.** Textual's
  `App.suspend()` only resumes the terminal driver if the code inside its
  `with` block returns normally (its implementation has no try/finally
  around its internal `yield`). `play_stream()` called `player.play()`
  inside that block, and `player.play()` deliberately raises
  `TorrentStreamError` for a magnet stream with no `webtorrent`/`peerflix`
  installed — so the exception skipped Textual's resume/refresh entirely,
  leaving a blank, unresponsive terminal even though the app was still
  alive and the error was (uselessly) caught one level up. Player errors
  are now caught *inside* the `suspend()` block instead, so the terminal
  always comes back and the error actually reaches the toast/detail panel.
  Covered by a regression test that fails against the old code.
- Restyled search results/detail panel with a valid Textual theme and
  stylesheet. (Between 0.2.0 and this release the CSS briefly grew
  web-only properties Textual doesn't support — gradients, animations,
  box-shadow, `:root` custom properties — which failed to parse and were
  worked around by disabling all custom styling. Rewritten from scratch
  using only Textual's actual CSS subset.)
- Removed a poster-art loading path that always silently failed
  (`textual.image` isn't part of the installed Textual version) and just
  added latency; replaced with the icon-based poster card that actually
  renders
- Config download directory now properly loaded from config.toml
- License format in pyproject.toml

## [0.2.0] - 2026-09-26

### Added
- **Stremio source** (Cinemeta catalogue + Torrentio streams)
- Movie, series, and anime search via Cinemeta API
- Episode picker for series/anime
- Quality picker with seeders/size display
- Magnet link playback via webtorrent/peerflix
- Debrid support (RealDebrid, AllDebrid, Premiumize, etc.)
- Watch history and library (favorites)
- Downloads via yt-dlp
- Local files source
- Config via config.toml and env vars
- MIT license

### Changed
- Renamed from `stream-tui` to `torrentio-tui`
- Package structure: `stream_tui` → `torrentio_tui`
- CLI command: `stream-tui` → `torrentio-tui`
- Config directory: `~/.config/stream-tui` → `~/.config/torrentio-tui`
- Env vars: `STREAM_TUI_*` → `TORRENTIO_TUI_*`

## [0.1.0] - 2026-09-26

### Added
- Initial scaffold with Textual TUI
- Local files source
- Basic search, episode/quality selection
- Playback via mpv/vlc
- Watch history and library
- Plugin architecture for sources

[0.3.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yubiiixtreme/torrentio-tui/releases/tag/v0.1.0