# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-26

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