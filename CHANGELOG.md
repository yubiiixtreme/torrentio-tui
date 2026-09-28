# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Verified every source live; fixed what was actually broken:**
  `comet` default moved to `https://comet.elfhosted.com`
  (`comet.strem.io` no longer resolves); `yts` moved to the API's
  current base `https://movies-api.accel.li/api/v2` (`yts.mx` is dead);
  `kitsu` now sends the `application/vnd.api+json` Accept header the
  API requires (was HTTP 406 on every call); transient HTTP 5xx on
  catalogue/torrent-index fetches is retried once; HTTP 403 from *any*
  addon now carries the proxy/configured-URL hint (was Torrentio-only).
- **Removed two more dead sources:** `rarbg` (`torrentapi.org`
  returns HTTP 400 — API gone with the 2023 shutdown) and
  `nuviostreams` (public instance serves its SPA at `/manifest.json`).
- **Multilingual playback:** mpv now gets `--slang/--alang` from the
  `[language]` preferences (HUD mode included), so matching audio and
  subtitle tracks auto-select instead of always defaulting to the
  first track.

### Added
- **Source categories** — every source now declares a category
  (`streams`, `catalogue`, `anime`, `live`, `local`, `adult`);
  `--list-sources`, the in-app `?` help, and the config template all
  render the same grouping, generated from the registry so docs never
  go stale.
- **More stream addons** (all speaking Stremio's `/stream/` protocol):
  `aiostreams` (80+ addon super-addon), `stremthru` (debrid-store
  catalog), `jackettio` (Jackett trackers via debrid), `nuviostreams`
  (direct HTTP, no debrid needed), `deflix` and `stremify`
  (self-hosted). All honour per-source `[sources.<id>]` overrides and
  the global proxy.
- **Real torrent-index sources**: `yts` reimplemented against the
  official YTS API and `rarbg` against `torrentapi.org` (token handling
  + rate-limit throttling built in) — both return genuine playable
  magnets instead of dead website URLs.
- **Catalogue providers**: `tvmaze` (series air-dates/episodes),
  `jikan` (MyAnimeList anime), `kitsu` (Kitsu anime) — free, keyless,
  and playable: TVMaze bridges via IMDb ids, all three fall back to a
  Cinemeta title resolve through your configured stream addon.
- **Subtitle providers** (`[subtitles]`, opt-in): `subdb` (keyless
  hash match for local files) and `opensubtitles` (API key + optional
  login) behind a plugin interface; playback auto-attaches the best
  preferred-language caption, cached locally for mpv/vlc.
- **Theme persistence for every path** — any theme change (`t`
  cycling *and* the Ctrl+P picker) is watched and saved, so the pick
  is the default next launch.

### Removed
- `debridmediamanager` (a web app, not a Stremio addon — it
  could never return streams) from the registry and the default
  `enabled` list, and the never-functional website-URL
  "addons" (`eztv`, `1337x`, `horriblesubs`, `subscene`,
  `opensubtitles`-as-streams). Old configs referencing them skip
  gracefully.
- `knightcrawler` default URL updated (project ceased 2024, public
  instance retired) and marked deprecated in docs.

### Fixed
- **Startup no longer dies on corrupt state** — a half-written
  `history.json`/`library.json` (crash mid-save) or malformed
  `config.toml` now backs up/falls back to defaults instead of raising
  an uncaught `JSONDecodeError`/`TOMLDecodeError`; saves are atomic
  (write-temp-then-rename) so the corrupt state can't recur.
- **Subtitle picker (`s`) no longer crashes** — `_get_lang_name`
  iterated dict keys and read `.value` off a `str`
  (`AttributeError` on open); now looks up `SUBTITLE_LANGUAGE_CODES`
  directly. The ✓ marker also no longer appears on every row, and
  subtitle/UI-language picks actually apply (top preference / session
  language) instead of being silently dropped.
- **Failed playback is no longer recorded as "watched"** — the blocking
  player path ignored the exit code and the HUD path only surfaced
  spawn errors; non-zero exits now surface as errors (user-initiated
  HUD stops still count as watched).
- **`nhentai`/`rule34` sources are now registered and usable** (they
  were implemented but missing from the registry), with payload guards:
  int-timestamp `upload_date`, real `images.thumbnail`/`media_id`
  covers, dict-shaped Rule34 error payloads, and empty Hanime URLs
  skipped.
- **`comet`/`debridmediamanager` (and all `StremioSource` subclasses)
  now honour per-source config + proxy** — the registry matched only
  exact `StremioSource`, so these silently fell back to hardcoded
  defaults; dead unreachable branches removed.
- **`--doctor` probes every enabled Stremio-protocol addon** via the
  registry (was a hardcoded 4-id subset missing the default-enabled
  addons), and a gated adult source is a one-line diagnostic instead
  of a traceback — same for app startup.
- **UI freezes fixed** — blocking source I/O now runs via
  `asyncio.to_thread` instead of on the Textual event loop; HUD poll
  and mpv IPC tolerate malformed replies/socket hiccups per-tick
  instead of crashing the interval callback.
- **`terminate_group` no longer raises on a reaped child** (used to
  escape `os.getpgid` outside the `suppress`, fatal inside a signal
  handler).
- **Downloads**: `yt-dlp --add-header` now uses the `Key: value` format,
  and non-ASCII (CJK/anime) titles are preserved instead of collapsing
  to `video.%(ext)s`.
- **VLC forwards auth headers** (`Authorization`, `Cookie`, ...) via
  `--http-header` instead of silently dropping everything but
  referrer/user-agent.
- **Config hardening**: `enabled_sources` accepts a bare string,
  non-dict tables are ignored, `save_theme` handles single quotes and
  a missing `[ui]` section (scoped to that section), and `Config`
  instances no longer share one mutable `LanguageConfig`.
- Repo-wide `ruff format` applied, so CI's format gate passes again.
- 20 new provider tests (catalogue, torrent-index, subtitles,
  categories, theme persistence).

## [0.4.0] - 2026-09-26

### Added
- **Real poster art** — `images.py`/`PosterWidget` now actually renders
  downloaded images (via the optional `textual-image` dependency,
  `pip install torrentio-tui[images]`), auto-detecting Kitty/iTerm2/Sixel
  graphics or falling back to a Unicode half-block approximation. Falls
  back to the existing colored icon card if the extra isn't installed or
  a poster fails to download — always shows *something*.
- **Theme cycling** — press `t` to cycle a curated set (`torrentio`,
  `dracula`, `nord`, `gruvbox`, `catppuccin-mocha`, `tokyo-night`,
  `monokai`); the choice is saved to `[ui] theme` in config.toml and
  restored on next launch. Full Textual theme list still available via
  the command palette (Ctrl+P).
- `mediafusion` enabled by default alongside `stremio`, so one provider
  being down/blocked doesn't leave a fresh install with zero results;
  results from each are tagged with their own colored source badge.

### Fixed
- **`?` (help) crashed the app.** `HelpScreen` mounted three `Static`
  widgets with `id="help-title"` and three with `id="help-body"` in the
  same container — Textual requires unique ids per parent, so opening
  help raised `MountError: Tried to insert 3 widgets with the same ID`.
  Never caught anywhere, so this would have taken the whole app down the
  first time anyone pressed `?`. Switched to CSS classes instead of ids.
- **Poster art never actually rendered.** The previous implementation set
  `self.styles.background_image = "url(...)"` — not a real Textual CSS
  property (that's web CSS); it silently did nothing. Replaced with an
  actual rendering pipeline.
- **`StremioSource` id collision** (from a couple of commits back) —
  every config entry that maps to `StremioSource` (`stremio`,
  `mediafusion`, `knightcrawler`, `torrentio-selfhost`) reported the
  same hardcoded class-level `id`, so clicking any result always
  resolved back to whichever loaded first regardless of which one
  actually produced it. Each instance now gets its own id.
- **`webtorrent-cli --title` flag doesn't exist** — every magnet click
  built a command with a flag this webtorrent-cli version rejects
  outright (`Error: Unknown argument: title`), crashing before it ever
  touched the network. Removed; player.play()'s exit code is also no
  longer silently ignored, so a streamer crash now surfaces as a real
  error instead of being recorded as "watched."

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

[0.4.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yubiiixtreme/torrentio-tui/releases/tag/v0.1.0