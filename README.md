# Torrentio TUI(STILL IN DEVELOPMENT NOT WORKING)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/yubiiixtreme/torrentio-tui/workflows/CI/badge.svg)](https://github.com/yubiiixtreme/torrentio-tui/actions)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A terminal UI for discovering and streaming **movies, series & anime** —
search a catalogue, pick an episode, pick a quality, and it plays instantly
in **mpv / vlc** on your own machine.

Built with Python + [Textual](https://textual.textualize.io/). Inspired by
[MovieBox-TUI](https://github.com/mesamirh/MovieBox-TUI) (multi-source feel)
and [ani-cli](https://github.com/pystardust/ani-cli) (search → pick → mpv).

## Screenshots

*Coming soon — run `torrentio-tui` to see the beautiful Textual TUI!*

## Features

- 🔍 **Catalogue search** — movies, series & anime via
  [Cinemeta](https://v3-cinemeta.strem.io/manifest.json)
- 🎬 **One-key playback** — streams resolve via
  [Torrentio](https://torrentio.strem.fun/configure) (or any compatible
  Stremio addon) and play in mpv/vlc
- 📺 **Episode & quality picker** — full season/episode lists, qualities
  ranked with seeders and size
- 📚 **Continue watching + library** — history and favorites stored locally
- ⬇️ **Downloads** via `yt-dlp` for direct http streams
- 🔌 **Plugin sources** — new sources drop in without touching UI/player code
- 💾 **Local files source** — index and play your own `~/Videos` folder

## Requirements

| What | Why | Install |
|------|-----|---------|
| Python 3.10+ | runs the app | `python3 --version` |
| `mpv` **or** `vlc` | video playback (desktop/Linux/macOS) | `sudo apt install mpv` / `sudo dnf install mpv` / `brew install mpv` |
| `webtorrent-cli` *(optional)* | plays magnet links without a debrid key | `npm install -g webtorrent-cli` |
| `yt-dlp` *(optional)* | downloads | `pip install yt-dlp` |

Run `torrentio-tui --doctor` any time to check what's installed and where
your config file lives.

> **Debrid shortcut:** add a RealDebrid / AllDebrid / Premiumize key to your
> Torrentio configure URL and you get direct http links — no torrent
> streamer needed. See [Torrentio setup](#torrentio-setup) below.

## Installation

### Option 1 — pip from GitHub (recommended)

```
pip install git+https://github.com/yubiiixtreme/torrentio-tui.git
torrentio-tui
```

### Option 2 — pipx (isolated, stays on PATH)

```
pipx install git+https://github.com/yubiiixtreme/torrentio-tui.git
torrentio-tui
```

### Option 3 — from source

```
git clone https://github.com/yubiiixtreme/torrentio-tui.git
cd torrentio-tui
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/torrentio-tui
```

### Option 4 — PyPI (once the first release is published)

```
pip install torrentio-tui
torrentio-tui
```

### Termux (Android)

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

1. Launch `torrentio-tui`.
2. Type a title in **Search** and hit Enter — e.g. `breaking bad`.
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

[sources]
enabled = ["stremio", "local"]

[sources.stremio]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://torrentio.strem.fun"
timeout_seconds = 15.0

[network]
# proxy_url = "socks5://127.0.0.1:40000"   # see "Routing around the 403"

[downloads]
directory = "~/Videos/torrentio-tui"
```

| Env var | Purpose |
|---------|---------|
| `TORRENTIO_TUI_STREAM_URL` | custom stream addon URL |
| `TORRENTIO_TUI_CINEMETA_URL` | custom Cinemeta base |
| `TORRENTIO_TUI_TIMEOUT` | HTTP timeout (seconds) |
| `TORRENTIO_TUI_PROXY` / `--proxy` | proxy URL for Cinemeta/Torrentio requests |
| `TORRENTIO_TUI_PLAYER` / `--player` | `mpv`, `vlc`, `termux`, or `vlc-android` |
| `TORRENTIO_TUI_HWDEC` / `--hwdec` | mpv `--hwdec` mode (`auto-safe`, `auto`, `""` to disable) |
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

## Keybindings

| Key | Action |
|-----|--------|
| `Enter` | search / open selected item |
| `↑` / `↓` | move selection; `Tab` switches focus between panes |
| `l` | save / unsave highlighted result to Library |
| `d` | download the highlighted result (needs `yt-dlp`) |
| `i` | quick info popup for the highlighted result |
| `?` | show the in-app keybindings help |
| `Esc` | back out of episode / quality / help dialogs |
| `q` | quit |

## Project layout

```
torrentio_tui/
  models.py        # Source-agnostic data types: SearchResult, Episode, StreamLink, HistoryEntry
  config.py        # XDG config/data/cache paths, config.toml loading
  termux.py        # Termux (Android) environment detection
  proxy.py         # Optional outbound proxy (http/https/socks5) for Cinemeta/Torrentio
  history.py       # "Continue watching" store (JSON)
  library.py       # Saved/favorites store (JSON)
  downloads.py     # Batch download via yt-dlp subprocess
  cli.py           # Entry point (`torrentio-tui`), argument parsing, --doctor

  sources/
    base.py        # Source ABC — the plugin contract (search / get_episodes / get_streams)
    stremio.py     # Cinemeta catalogue + Torrentio-style streams (movie/series/anime)
    local.py       # Indexes a local media folder
    example.py     # Annotated template for a real scraper/API source (not registered)
    registry.py    # Maps config source ids -> Source classes

  player/
    base.py        # Player ABC
    mpv.py, vlc.py # Subprocess backends (headers, subtitles, resume, mpv hwdec)
    termux.py      # Hands the stream URL to Android via termux-open (any registered app)
    vlc_android.py # Launches VLC for Android directly via an `am start` intent
    torrent.py     # magnet: → webtorrent/peerflix bridge for mpv/vlc
    registry.py    # Maps config backend id -> Player

  ui/
    app.py                  # Textual App + theme
    screens/main.py         # Search / Continue Watching / Library tabs
    screens/episodes.py     # Episode picker modal
    screens/quality.py      # Quality/stream picker modal
    screens/help.py         # Keybindings help modal ('?')
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
git tag v0.3.0 && git push --tags
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

## License

MIT — see [LICENSE](LICENSE).
