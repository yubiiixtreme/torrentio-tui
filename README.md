# stream-tui

A terminal UI for discovering and streaming **movies, series & anime** —
search a catalogue, pick an episode, pick a quality, and it plays instantly
in **mpv / vlc** on your own machine.

Built with Python + [Textual](https://textual.textualize.io/). Inspired by
[MovieBox-TUI](https://github.com/mesamirh/MovieBox-TUI) (multi-source feel)
and [ani-cli](https://github.com/pystardust/ani-cli) (search → pick → mpv).

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
| `mpv` **or** `vlc` | video playback | `sudo apt install mpv` / `sudo dnf install mpv` / `brew install mpv` |
| `webtorrent-cli` *(optional)* | plays magnet links without a debrid key | `npm install -g webtorrent-cli` |
| `yt-dlp` *(optional)* | downloads | `pip install yt-dlp` |

> **Debrid shortcut:** add a RealDebrid / AllDebrid / Premiumize key to your
> Torrentio configure URL and you get direct http links — no torrent
> streamer needed. See [Torrentio setup](#torrentio-setup) below.

## Installation

### Option 1 — pip from GitHub (recommended)

```
pip install git+https://github.com/yubiiixtreme/stream-tui.git
stream-tui
```

### Option 2 — pipx (isolated, stays on PATH)

```
pipx install git+https://github.com/yubiiixtreme/stream-tui.git
stream-tui
```

### Option 3 — from source

```
git clone https://github.com/yubiiixtreme/stream-tui.git
cd stream-tui
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/stream-tui
```

### Option 4 — PyPI (once the first release is published)

```
pip install stream-tui
stream-tui
```

## Quickstart

1. Launch `stream-tui`.
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
   `~/.config/stream-tui/config.toml` (or `STREAM_TUI_STREAM_URL`).

Without a debrid key you get `magnet:` links — install `webtorrent-cli`
and the app streams them into mpv/vlc automatically.

> ⚠️ Torrentio Cloudflare-blocks some datacenter/VPN IPs (HTTP 403). On a
> blocked network the app tells you — switch to a residential IP, self-host
> Torrentio, or point `stream_url` at another compatible addon.

## Configuration

Config lives at `~/.config/stream-tui/config.toml` (created on first run);
history/library at `~/.local/share/stream-tui/`. Env vars always win.

```toml
[player]
backend = "mpv"          # mpv | vlc
default_quality = "1080p"

[sources]
enabled = ["stremio", "local"]

[sources.stremio]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://torrentio.strem.fun"
timeout_seconds = 15.0

[downloads]
directory = "~/Videos/stream-tui"
```

| Env var | Purpose |
|---------|---------|
| `STREAM_TUI_STREAM_URL` (`STREAM_TUI_TORRENTIO_URL` also works) | custom stream addon URL |
| `STREAM_TUI_CINEMETA_URL` | custom Cinemeta base |
| `STREAM_TUI_TIMEOUT` | HTTP timeout (seconds) |
| `STREAM_TUI_PLAYER` / `--player` | `mpv` or `vlc` |
| `STREAM_TUI_LOCAL_DIR` | folder indexed by the `local` source (default `~/Videos`) |
| `STREAM_TUI_DOWNLOAD_DIR` | download folder |

Useful commands:

```
stream-tui --player vlc      # one-off backend override
stream-tui --list-sources    # show registered source ids
```

## Keybindings

| Key | Action |
|-----|--------|
| `Enter` | search / open selected item |
| `l` | save / unsave highlighted result to Library |
| `Esc` | back out of episode / quality dialogs |
| `q` | quit |

## Project layout

```
stream_tui/
  models.py        # Source-agnostic data types: SearchResult, Episode, StreamLink, HistoryEntry
  config.py        # XDG config/data/cache paths, config.toml loading
  history.py       # "Continue watching" store (JSON)
  library.py       # Saved/favorites store (JSON)
  downloads.py     # Batch download via yt-dlp subprocess
  cli.py           # Entry point (`stream-tui`), argument parsing

  sources/
    base.py        # Source ABC — the plugin contract (search / get_episodes / get_streams)
    stremio.py     # Cinemeta catalogue + Torrentio-style streams (movie/series/anime)
    local.py       # Indexes a local media folder
    example.py     # Annotated template for a real scraper/API source (not registered)
    registry.py    # Maps config source ids -> Source classes

  player/
    base.py        # Player ABC
    mpv.py, vlc.py # Subprocess backends (headers, subtitles, resume)
    torrent.py     # magnet: → webtorrent/peerflix bridge for mpv/vlc
    registry.py    # Maps config backend id -> Player

  ui/
    app.py                  # Textual App
    screens/main.py         # Search / Continue Watching / Library tabs
    screens/episodes.py     # Episode picker modal
    screens/quality.py      # Quality/stream picker modal
```

## Adding another source

1. Copy `stream_tui/sources/example.py` to e.g.
   `stream_tui/sources/myscraper.py` and implement `search()`, optionally
   `get_episodes()`, and `get_streams()`. Return `StreamLink`s with any
   `headers` (Referer/User-Agent/cookies) the CDN needs — the player
   backends forward those automatically.
2. Register it in `stream_tui/sources/registry.py`:
   ```python
   from stream_tui.sources.myscraper import MyScraperSource
   _AVAILABLE["myscraper"] = MyScraperSource
   ```
3. Add `"myscraper"` to `sources.enabled` in
   `~/.config/stream-tui/config.toml`.

The rest of the app — search UI, episode/quality modals, playback, history,
downloads — needs no changes; it only ever talks to the `Source`/`StreamLink`
abstractions in `models.py` and `sources/base.py`.

## Development & tests

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/stream-tui
```

To cut a release:

```
.venv/bin/python -m build
.venv/bin/python -m twine upload dist/*
git tag v0.2.0 && git push --tags
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
