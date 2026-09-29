<div align="center">

# 🎬 Torrentio TUI

### **Netflix, but it's your terminal.** 🍿

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20Android-lightgrey.svg)](#installation)
[![Sources](https://img.shields.io/badge/sources-53%20free-gold.svg)](#features)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/yubiiixtreme/torrentio-tui/workflows/CI/badge.svg)](https://github.com/yubiiixtreme/torrentio-tui/actions)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![GitHub stars](https://img.shields.io/github/stars/yubiiixtreme/torrentio-tui?style=flat&color=gold)](https://github.com/yubiiixtreme/torrentio-tui/stargazers)

[✨ Features](#features) · [📦 Install](#installation) · [🚀 Quickstart](#quickstart) · [⌨️ Keybindings](#keybindings) · [🆘 Troubleshooting](#troubleshooting)

</div>

It opens on 🔥 **Trending** so there's always something to watch —
search movies, series and anime across **53 free sources** at once,
funnel the results by kind, category, genre, year and sort, pick a
quality, and it's playing in mpv/vlc seconds later. Real poster art
rendered inline, your pick of color themes, everything stored locally
on your own machine. No account, no tracking, no ads.

```
 ┌ sidebar ────────┐ ┌─ 🔥 Trending ─────────────────────────┐
 │ 🔍 Search       │ │ 🎬 Dune: Part Two (2024)  [stremio]   │
 │ 🔥 Trending     │ │ 📺 Breaking Bad (2008)    [stremio]   │
 │ ❤️ Library      │ │ 🎴 Solo Leveling (2024)   [anilist]   │
 │ ⏯ Continue      │ │                                       │
 │ 🔌 Sources 4/53 │ │ Enter to play · l to save · i info    │
 └─────────────────┘ └───────────────────────────────────────┘
  1-5 sections · / search · ⩔ funnel · g settings · t theme · ? help
```

New here? Jump to **[Quickstart](#quickstart)** — three commands and
you're watching something.

Built with Python + [Textual](https://textual.textualize.io/). Concept
inspired by [MovieBox-TUI](https://github.com/mesamirh/MovieBox-TUI)
(multi-source feel) and [ani-cli](https://github.com/pystardust/ani-cli)
(search → pick → mpv), built independently on top of the Stremio addon
ecosystem (Cinemeta + Torrentio-compatible stream addons).

## Features

- 🔍 **Search 53 free sources at once** — every enabled provider
  (Torrentio, MediaFusion, Comet, AIOStreams, Torrentio Cloud,
  SuperStream, YTS, RARBG, 1337x, Pirate Bay, EZTV, LimeTorrents,
  Nyaa, AniDex, TVMaze, TMDB, Trakt, Jikan, Kitsu, AniList, free
  world IPTV, your own self-hosted instance, ...) is queried and
  results are merged, each tagged with a colored source badge, so one
  provider being down or blocked never leaves you with zero results.
  Sources are grouped into categories (streams, catalogue, anime,
  live, local, adult) — see `torrentio-tui --list-sources`
- 🖼️ **Real poster art**, rendered inline in your terminal (Kitty/iTerm2/
  Sixel graphics where supported, a Unicode-block approximation
  everywhere else) — not ASCII placeholders, actual cached images, with
  ghost-image cleanup on the Kitty Graphics Protocol so switching results
  never leaves a stale poster behind
- 🎨 **Pick your theme** — press `t` to cycle a curated set (a built-in
  cinematic gold/red theme and a true-black OLED theme, plus Dracula,
  Nord, Gruvbox, Catppuccin Mocha/Latte, Tokyo Night, Monokai), or drop
  your own JSON theme file in `~/.config/torrentio-tui/themes/` — no
  restart needed, it's picked up the next time you cycle. Any theme you
  pick (cycling or the Ctrl+P picker) is saved and becomes the default
  next launch
- 📊 **Live playback HUD** *(opt-in, `[player] hud = true`)* — buffer
  health and cache-speed sparkline in-app instead of a full-screen mpv,
  with pause/seek/stop keys (needs mpv's own GUI window; see
  [Configuration](#configuration))
- ⌨️ **Vim-friendly navigation** — `j`/`k` alongside the arrow keys in
  every list, `/` jumps straight to the search box
- 🎬 **One-key playback** — streams resolve via
  [Torrentio](https://torrentio.strem.fun/configure) (or any compatible
  Stremio addon) and play in mpv/vlc
- ⩔ **Funnel filters** — kind, category, genre, year and sort filter
  fetched results instantly (press `f`); result counts shown live
- 🔥 **Trending tab** — top movies & series with zero typing
- 📺 **Episode & quality picker** — full season/episode lists with live
  search, `/` to focus, digit keys jump to seasons; qualities ranked
  with seeders and size
- ⚙️ **Settings screen** (press `g`) — adult-content lock (off by
  default), theme picker, player backend, subtitles, download folder —
  everything persisted to `config.toml` automatically
- 💬 **Auto-subtitles** *(opt-in, `[subtitles] enabled = true`)* —
  SubDB (keyless) and OpenSubtitles.com providers attach the best
  preferred-language caption to streams missing one, cached locally so
  mpv/vlc always get a file path
- 📚 **Continue watching + library** — history and favorites stored locally
- ⬇️ **Downloads** via `yt-dlp` for direct http streams, with a live
  percent/speed/ETA status line instead of just a start/end notification
- 📱 **Works on Android via Termux** — auto-detected, hands playback off
  to VLC/your video app since Termux has no display of its own
- 🩺 **Self-diagnosing** — `--doctor` checks every tool it depends on and
  live-probes whether your sources are actually reachable
- 🔌 **Plugin sources** — new sources drop in without touching UI/player code
- 💾 **Local files source** — index and play your own `~/Videos` folder
- 🛑 **Clean process lifecycle** — mpv/vlc/webtorrent/peerflix/yt-dlp are
  spawned in their own process group and reaped on Ctrl-C or app exit;
  network calls (poster fetches) retry transient failures with backoff

## Requirements

| What | Why | Install |
|------|-----|---------|
| Python 3.10+ | runs the app | `python3 --version` |
| `mpv` **or** `vlc` | video playback (desktop/Linux/macOS) | `sudo apt install mpv` / `sudo dnf install mpv` / `brew install mpv` |
| `webtorrent-cli` *(optional)* | plays magnet links without a debrid key | `npm install -g webtorrent-cli` |
| `yt-dlp` *(optional)* | downloads | `pip install yt-dlp` |
| `textual-image` *(optional)* | real poster art instead of icon cards | `pip install "torrentio-tui[images]"` |

Run `torrentio-tui --doctor` any time to check what's installed and where
your config file lives.

> **Debrid shortcut:** add a RealDebrid / AllDebrid / Premiumize key to your
> Torrentio configure URL and you get direct http links — no torrent
> streamer needed. See [Torrentio setup](#torrentio-setup) below.

## Installation

> ✅ **Requires Python 3.10 or newer — any newer 3.x works**
> (3.11, 3.12, 3.13, 3.14, ...). Check yours first:
> `python3 --version`
>
> ⚠️ **Golden rule: install and run with the SAME Python.**
> Always use `python3 -m pip ...` (not bare `pip`, which may belong
> to a different Python) — mixing interpreters is the #1 cause of
> `ModuleNotFoundError`. See [Troubleshooting](#troubleshooting).

### 🐧 Linux

```bash
# Debian/Ubuntu: sudo apt install python3 python3-pip python3-venv mpv
# Fedora:        sudo dnf install python3 python3-pip mpv

pipx install "torrentio-tui[images] @ git+https://github.com/yubiiixtreme/torrentio-tui.git"
torrentio-tui
```

No pipx? `python3 -m pip install --user "torrentio-tui[images] @
git+https://github.com/yubiiixtreme/torrentio-tui.git"` — then make
sure `~/.local/bin` is on your `PATH`.

Drop `[images]` for a lighter install without real poster art (icon
cards instead) — everything else is identical.

### 🍎 macOS

```bash
brew install python mpv pipx
pipx ensurepath   # then restart your terminal once
pipx install "torrentio-tui[images] @ git+https://github.com/yubiiixtreme/torrentio-tui.git"
torrentio-tui
```

Prefer VLC? `brew install --cask vlc` and set `--player vlc` (or
`player.backend = "vlc"` in the config).

### 🪟 Windows (PowerShell)

```powershell
# 1. Install Python 3.10+ from python.org — tick "Add python.exe to PATH"
# 2. Install mpv: winget install mpv  (or VLC: winget install VideoLAN.VLC)
py -m pip install "torrentio-tui @ git+https://github.com/yubiiixtreme/torrentio-tui.git"
torrentio-tui
```

> Use `py -m pip` (not `pip`) so the package lands in the same Python
> that runs it.

### 🛠️ From source (developers, any OS)

```
git clone https://github.com/yubiiixtreme/torrentio-tui.git
cd torrentio-tui
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/torrentio-tui
```

### 📦 PyPI (once the first release is published)

```
pip install torrentio-tui
torrentio-tui
```

### 🤖 Termux (Android)

Termux is headless (no video output of its own), so playback works
differently there: instead of running mpv in the terminal, the app hands
the stream URL to Android via `termux-open`, which opens it in whatever
video app you have installed (VLC, MX Player, ...) — the same approach
ani-cli uses on Android.

```bash
pkg update
pkg install python termux-api
pip install pipx
pipx ensurepath && source ~/.bashrc     # or restart Termux
pipx install git+https://github.com/yubiiixtreme/torrentio-tui.git
```

Also install the **Termux:API** companion app (from
[F-Droid](https://f-droid.org/packages/com.termux.api/) or the Play Store —
must match your Termux install source) so `termux-open` can hand links to
other apps.

```
torrentio-tui --doctor    # confirms termux-open is wired up
torrentio-tui
```

The player backend defaults to `termux` automatically when running inside
Termux (detected via `$TERMUX_VERSION`) — no config needed. Downloads
(`yt-dlp`, pure Python) and the `local`/`stremio` sources work the same as
on desktop. Magnet-only streams (no debrid key configured) generally won't
open this way — either configure a debrid key in your Torrentio addon URL
(see [Torrentio setup](#torrentio-setup)) or install a torrent app that
registers as a magnet handler.

**Prefer VLC specifically?** Set `--player vlc-android` (or
`player.backend = "vlc-android"` in config.toml). Instead of asking
Android to pick whatever app is registered for video (which can pop an
app-chooser dialog), it launches VLC for Android directly via an `am
start` intent and passes along the resume position. Needs VLC for Android
installed — `torrentio-tui --doctor` checks for it.

## Quickstart

1. Launch `torrentio-tui` — you land on 🔥 **Trending** (already full).
2. Type a title in **Search** (press `1` or `/`) and hit Enter — e.g. `breaking bad`.
3. Select the show/movie → pick an episode (series/anime) → pick a quality.
4. mpv (or vlc) opens and plays. Press `l` on a highlighted result to
   save/unsave it to your **Library**; resume from **Continue Watching**.

```
Search "dune" → Dune: Part Two (2024) [stremio]
  → quality: 1080p BLURAY 👤120 💾1.8GB → mpv opens ▶
```

## Torrentio setup

The default `stremio` source splits the job the standard Stremio way:

- **Catalogue:** Cinemeta (`/catalog/{movie,series}/top/search=...` for
  search, `/meta/...` for episodes). Anime is auto-classified from genres
  and behaves like series.
- **Streams:** Torrentio (`/stream/{movie,series}/{imdbVideoId}.json`).
  Any compatible addon URL works — MediaFusion, Knightcrawler, or a
  self-hosted Torrentio.

**For the best experience** (direct links, no torrent client):

1. Open `https://torrentio.strem.fun/configure`.
2. Pick providers, paste your RealDebrid/AllDebrid/Premiumize API key.
3. Copy the configured URL and set it as `sources.stremio.stream_url` in
   `~/.config/torrentio-tui/config.toml` (or `TORRENTIO_TUI_STREAM_URL`).

Without a debrid key you get `magnet:` links — install `webtorrent-cli`
and the app streams them into mpv/vlc automatically.

> ⚠️ Torrentio Cloudflare-blocks some datacenter/VPN IPs (HTTP 403). On a
> blocked network the app tells you — either point `stream_url` at another
> compatible addon / self-host Torrentio, or route requests through a proxy
> (see [Routing around the 403](#routing-around-the-403) below).

### Routing around the 403

If the official Stremio app works for you on the same network but
torrentio-tui gets blocked, it's almost always that Stremio's app and this
CLI are leaving from different IPs (a VPN active for one but not the
other, a container/remote box without your usual VPN, etc). Point
`network.proxy_url` at whatever gives Torrentio a clean IP — for example
[Cloudflare WARP](https://developers.cloudflare.com/warp-client/) in proxy
mode, which runs a local SOCKS5 proxy without taking over your whole
system's routing the way WARP's VPN mode does:

```bash
warp-cli mode proxy        # one-time: switch WARP to local-proxy mode
warp-cli set-proxy-port 40000
warp-cli connect
```

```toml
# ~/.config/torrentio-tui/config.toml
[network]
proxy_url = "socks5://127.0.0.1:40000"
```

Or one-off, without touching the config file: `torrentio-tui --proxy
socks5://127.0.0.1:40000`. A plain HTTP/HTTPS proxy (`http://host:port`)
works too and needs nothing extra installed; `socks5://` needs
[PySocks](https://pypi.org/project/PySocks/) — install with
`pip install pysocks` or `pip install "torrentio-tui[proxy]"`.
`torrentio-tui --doctor` confirms whether a proxy is configured, whether
PySocks is available, and — unless run with `--offline` — actually probes
Cinemeta and your configured stream addon so you can see whether *you're*
currently blocked before you even try to search.

## Configuration

Config lives at `~/.config/torrentio-tui/config.toml` (created on first run);
history/library at `~/.local/share/torrentio-tui/`. Env vars always win.

```toml
[player]
backend = "mpv"          # mpv | vlc | termux | vlc-android
default_quality = "1080p"
hwdec = "auto-safe"       # mpv hardware decoding; "" to disable, "auto" for more aggressive
hud = false               # live buffer/speed HUD instead of full-screen mpv -- see "Live HUD mode" below

[ui]
theme = "torrentio"       # torrentio | oled-black | matrix | void | synthwave | amber | dracula | nord | gruvbox | catppuccin-mocha | catppuccin-latte | tokyo-night | monokai | <your custom theme's name>

[sources]
# Searched and merged — having more than one enabled means a
# single provider being down/blocked doesn't leave you with zero results.
# Full catalogue with categories: `torrentio-tui --list-sources`.
enabled = ["stremio", "mediafusion", "comet", "local"]

[sources.stremio]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://torrentio.strem.fun"
timeout_seconds = 15.0

[sources.mediafusion]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://mediafusion.elfhosted.com"
timeout_seconds = 15.0

[sources.comet]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://comet.elfhosted.com"
timeout_seconds = 15.0

[subtitles]
enabled = false            # auto-attach SubDB/OpenSubtitles captions at playback
providers = ["subdb", "opensubtitles"]

[adult]
enabled = false            # adult sources stay locked until you opt in
                           # (also toggleable live via Settings with `g`)

[network]
# proxy_url = "socks5://127.0.0.1:40000"   # see "Routing around the 403"

[downloads]
directory = "~/Videos/torrentio-tui"
```

`torrentio-tui --list-sources` prints every source id grouped by category,
`?` inside the app lists the same grouping, and the full set of options
(stream addons, catalogue companions, anime-specific sources, subtitles,
adult content behind an explicit opt-in) is documented with examples in
the generated config file itself — open
`~/.config/torrentio-tui/config.toml` and read the comments.

| Env var | Purpose |
|---------|---------|
| `TORRENTIO_TUI_STREAM_URL` | custom stream addon URL |
| `TORRENTIO_TUI_CINEMETA_URL` | custom Cinemeta base |
| `TORRENTIO_TUI_TIMEOUT` | HTTP timeout (seconds) |
| `TORRENTIO_TUI_PROXY` / `--proxy` | proxy URL for Cinemeta/Torrentio requests |
| `TORRENTIO_TUI_PLAYER` / `--player` | `mpv`, `vlc`, `termux`, or `vlc-android` |
| `TORRENTIO_TUI_HWDEC` / `--hwdec` | mpv `--hwdec` mode (`auto-safe`, `auto`, `""` to disable) |
| `TORRENTIO_TUI_THEME` | color theme name (see `[ui]` above, or a custom theme's name) |
| `TORRENTIO_TUI_SUBTITLES` | `1`/`true` to enable auto-subtitles (same as `[subtitles] enabled`) |
| `TORRENTIO_TUI_OS_API_KEY` | OpenSubtitles.com API key |
| `TORRENTIO_TUI_HUD` | `1`/`true` to enable the live HUD (see below); same as `[player] hud` |
| `TORRENTIO_TUI_LOCAL_DIR` | folder indexed by the `local` source (default `~/Videos`) |
| `TORRENTIO_TUI_DOWNLOAD_DIR` | download folder |

Useful commands:

```
torrentio-tui --player vlc                        # one-off backend override
torrentio-tui --proxy socks5://127.0.0.1:40000     # one-off proxy override
torrentio-tui --list-sources    # show registered source ids
torrentio-tui --doctor          # check tools + config, and probe whether Cinemeta/Torrentio are reachable
torrentio-tui --doctor --offline  # same, without the live reachability probe
torrentio-tui --version         # print the installed version
```

### Themes

Cycle the curated list with `t`, or `Ctrl+P` → `theme` for the full
picker (every registered theme, curated or not). The curated cycle is
`torrentio`, `dracula`, `nord`, `gruvbox`, `catppuccin-mocha`,
`catppuccin-latte`, `tokyo-night`, `monokai`, `oled-black`, plus any
custom theme you've added.

To add your own, drop a JSON file in `~/.config/torrentio-tui/themes/`:

```json
{
  "name": "sunset",
  "dark": true,
  "primary": "#FF8800",
  "accent": "#E11D48",
  "background": "#1A0F0A"
}
```

Every field but `name` is optional — anything you leave out falls back
to Textual's own theme defaults. No restart needed: the themes directory
is re-scanned each time you press `t` or open the theme picker, so
editing the file and cycling again picks up the change immediately.

### Live HUD mode

By default, playback hands mpv/vlc the whole terminal (`App.suspend()`)
— the classic "screen goes dark until the player quits" behavior. Set
`[player] hud = true` (mpv only) to instead run mpv backgrounded behind
its own GUI window, driven over its JSON IPC socket, while the app stays
up and shows a live buffer-health bar and cache-speed sparkline:

```toml
[player]
backend = "mpv"
hud = true
```

**Needs mpv's own window** (X11/Wayland/macOS/Windows) — leave it off on
a headless/SSH-only box, or for magnet/torrent streams (webtorrent/
peerflix don't expose an equivalent IPC, so those always use the
classic full-screen path regardless of this setting). While the HUD is
up: `Space` pause/resume, `←`/`→` seek ±10s, `q`/`Esc` stop.

## Keybindings

| Key | Action |
|-----|--------|
| `Enter` | search / open selected item |
| `↑` / `↓` or `k` / `j` | move selection; `Tab` switches focus between panes |
| `1`–`5` | jump to sidebar section (Search / Trending / Continue / Library / Sources) |
| `/` | jump to the search box and select its contents |
| `f` | show/hide the ⩔ funnel (kind · category · genre · year · sort) |
| `g` | open Settings (adult lock, theme, player, subtitles, folders) |
| `l` | save / unsave highlighted result to Library |
| `d` | download the highlighted result (needs `yt-dlp`) |
| `i` | quick info popup for the highlighted result |
| `t` | cycle color theme (saved automatically) |
| `s` | open the Sources section |
| `?` | show the in-app keybindings help |
| `Esc` | back out of episode / quality / help dialogs |
| `q` | quit |

In [Live HUD mode](#live-hud-mode): `Space` pause/resume, `←`/`→` seek
±10s, `q`/`Esc` stop.

## Project layout

```
torrentio_tui/
  models.py        # Source-agnostic data types: SearchResult, Episode, StreamLink, HistoryEntry
  config.py        # XDG config/data/cache paths, config.toml loading
  themes.py         # Custom theme loading (~/.config/torrentio-tui/themes/*.json)
  termux.py        # Termux (Android) environment detection
  proxy.py         # Optional outbound proxy (http/https/socks5) for Cinemeta/Torrentio
  images.py        # Poster download/cache + rendering (textual-image, optional)
  retry.py          # Exponential backoff helper for flaky network I/O
  history.py       # "Continue watching" store (JSON)
  library.py       # Saved/favorites store (JSON)
  downloads.py     # Batch download via yt-dlp subprocess
  cli.py           # Entry point (`torrentio-tui`), argument parsing, --doctor

  sources/
    base.py        # Source ABC — the plugin contract
                    # (search / get_episodes / get_streams / trending)
    stremio.py     # Cinemeta catalogue + Torrentio-style streams (movie/series/anime);
                    # also backs mediafusion/comet/aiostreams/stremthru/jackettio/
                    # deflix/stremify/nuviostreams/community/superstream/cloud/
                    # torrentio-selfhost (different stream_url each)
    free.py        # More Stremio-protocol addons (Comet, AIOStreams, StremThru,
                    # Jackettio, Deflix, Stremify, NuvioStreams, HorribleSubs,
                    # AniWorld, OtakuStream)
    extended.py    # EZTV, TorrentGalaxy, MagnetDL, Vumoo, SolarMovie,
                    # Stremio Community/SuperStream/Cloud
    rss_indexes.py # LimeTorrents, TorrentDownloads, GloDLS (RSS magnets)
    torrentapi.py  # YTS, RARBG, 1337x, Pirate Bay torrent indexes (magnets)
    torrent_extended.py  # TPB API, RARBG mirrors, Nyaa mirrors
    catalogues.py  # Metadata companions (TVMaze, Jikan, Kitsu, TMDB,
                    # Trakt) with playback bridged through your stream addon
    iptv.py        # Live TV from an M3U playlist + built-in free iptv-org world TV
    anime.py       # AniList metadata, Nyaa.si and SubsPlease torrents
    anime_extended.py  # AniDex, Anime Tosho, Tokyo Toshokan anime indexes
    adult.py + adult_extended.py  # Opt-in adult sources (locked by default)
    subtitles.py   # Subtitle providers (SubDB, OpenSubtitles) + auto-attach
    local.py       # Indexes a local media folder
    example.py     # Annotated template for a real scraper/API source (not registered)
    registry.py    # Maps config source ids -> Source classes (53 registered)

  player/
    base.py        # Player ABC
    process.py      # Signal-safe process group spawn/terminate (used by every backend below)
    mpv.py, vlc.py # Subprocess backends (headers, subtitles, resume, mpv hwdec)
    mpv_ipc.py       # mpv JSON-IPC client (backs the live HUD)
    termux.py      # Hands the stream URL to Android via termux-open (any registered app)
    vlc_android.py # Launches VLC for Android directly via an `am start` intent
    torrent.py     # magnet: → webtorrent/peerflix bridge for mpv/vlc
    registry.py    # Maps config backend id -> Player

  ui/
    app.py                  # Textual App + theme
    screens/main.py         # Sidebar + Search / Trending / Continue / Library / Sources views
    screens/settings.py     # Settings modal (adult lock, theme, player, subtitles, folders)
    screens/episodes.py     # Episode picker modal
    screens/quality.py      # Quality/stream picker modal
    screens/help.py         # Keybindings help modal ('?')
    screens/playback_hud.py  # Live HUD playback screen (opt-in, mpv only)
    widgets/                 # VimListView (j/k nav), StreamHud (buffer/speed HUD)
```

## Adding another source

1. Copy `torrentio_tui/sources/example.py` to e.g.
   `torrentio_tui/sources/myscraper.py` and implement `search()`, optionally
   `get_episodes()`, and `get_streams()`. Return `StreamLink`s with any
   `headers` (Referer/User-Agent/cookies) the CDN needs — the player
   backends forward those automatically.
2. Register it in `torrentio_tui/sources/registry.py`:
   ```python
   from torrentio_tui.sources.myscraper import MyScraperSource

   _AVAILABLE["myscraper"] = MyScraperSource
   ```
3. Add `"myscraper"` to `sources.enabled` in
   `~/.config/torrentio-tui/config.toml`.

The rest of the app — search UI, episode/quality modals, playback, history,
downloads — needs no changes; it only ever talks to the `Source`/`StreamLink`
abstractions in `models.py` and `sources/base.py`.

## Development & tests

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/torrentio-tui
```

To cut a release:

```
.venv/bin/python -m build
.venv/bin/python -m twine upload dist/*
git tag v0.4.0 && git push --tags
```

## Sources & legal note

Ships with `local` (your own files) and `stremio` (Cinemeta metadata +
user-configured Stremio stream addon). Only point a source at content you
actually have the right to access and relay through your player (an API
you're licensed for, your own media, sites whose terms permit this kind
of automated/programmatic access, etc). Torrentio-style addons scrape
third-party torrents — fetching infringing copies through them may violate
copyright law. That decision, and any debrid keys / self-hosting, is left
entirely to you.

## Troubleshooting

### `ModuleNotFoundError: No module named 'textual'` (or `'torrentio_tui'`)

Your app and your libraries live with **different Pythons**. Diagnose:

```bash
python3 --version
python3 -c "import sys,site; print(sys.path); print('USERSITE:', site.getusersitepackages())"
```

- If `python3 --version` differs between install time and run time
  (e.g. installed under 3.13, running 3.14), each Python has its own
  private folder — reinstall **with the Python you run**:
  `python3 -m pip install ...` (or `py -m pip ...` on Windows).
- Never mix bare `pip` with `python3` from another install. The
  `python3 -m pip` form makes mix-ups impossible.
- Still stuck? Force a clean reinstall for your exact interpreter:
  `python3 -m pip install --force-reinstall "torrentio-tui @
  git+https://github.com/yubiiixtreme/torrentio-tui.git"`.

### App looks old (no sidebar, no ⩔ funnel, footer nearly empty)

You're launching a **frozen copy** (e.g. an old `pipx` venv) instead of
the current code. Freshness check — this number grows with releases:

```bash
torrentio-tui --list-sources | wc -l    # ~59 lines at 53 sources
```

If it's much lower, refresh: `pipx reinstall torrentio-tui` (or
`pipx upgrade torrentio-tui`), or reinstall per [Installation](#installation).

### Torrentio blocked (HTTP 403) / empty results

See [Routing around the 403](#routing-around-the-403), and enable more
providers — press `g` → Sources, or edit `sources.enabled` in the
config. One blocked provider never means zero results when several are on.

## Uninstall & cleanup

torrentio-tui is a plain pip package — removing it is two steps:
uninstall the package, then (optionally) delete what it wrote to disk.
Config/data/cache paths are computed the same way on every OS (XDG-style,
via `~/.config` / `~/.local/share` / `~/.cache` — see `config.py`), so
the commands below are identical on Linux, macOS, *and* Windows once
you're in PowerShell; `~` expands to your home directory (`%USERPROFILE%`
on Windows) either way. If you set `XDG_CONFIG_HOME`/`XDG_DATA_HOME`/
`XDG_CACHE_HOME`, use those paths instead.

**1. Remove the package:**

```bash
pip uninstall torrentio-tui
# or, if you installed with pipx:
pipx uninstall torrentio-tui
```

**2. Remove its config, history/library, and cached poster images:**

Linux / macOS:

```bash
rm -rf ~/.config/torrentio-tui   # config.toml, custom themes/
rm -rf ~/.local/share/torrentio-tui   # history.json, library.json
rm -rf ~/.cache/torrentio-tui   # cached poster images
```

Windows (PowerShell):

```powershell
Remove-Item -Recurse -Force "$HOME\.config\torrentio-tui"
Remove-Item -Recurse -Force "$HOME\.local\share\torrentio-tui"
Remove-Item -Recurse -Force "$HOME\.cache\torrentio-tui"
```

If you also set a custom `[downloads] directory` and downloaded files
there, that folder (default `~/Videos/torrentio-tui`) isn't touched by
any of the above — remove it yourself if you want the downloaded media
gone too.

## License

MIT — see [LICENSE](LICENSE).
