# stream-tui

A terminal UI for discovering and streaming video content, built around a
small plugin interface so new sources can be dropped in without touching
the UI, player, history, or download code.

Concept borrowed from two references: the multi-source, multi-panel feel
of [MovieBox-TUI](https://github.com/mesamirh/MovieBox-TUI) (Rust/Ratatui),
and the "search -> pick -> pipe straight into mpv" simplicity of
[ani-cli](https://github.com/pystardust/ani-cli) (bash/fzf). This project
reimplements that *shape* in Python + [Textual](https://textual.textualize.io/),
with no scraping/source code included — see [Sources](#sources) below.

## Status

Runnable. Search, episode/quality selection, playback (mpv/vlc),
watch history, library (favorites), and downloads (via yt-dlp) are all
wired up against two sources:

* `stremio` (default) — movie/series/anime catalogue + search via
  Cinemeta, streams via any Stremio-protocol stream addon
  (Torrentio by default). Pick anything and it plays in mpv/vlc on
  your own machine.
* `local` — indexes a folder of video files on disk.

## Layout

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
    local.py        # Working reference source: indexes a local media folder
    example.py       # Annotated template for a real scraper/API source (not registered)
    registry.py     # Maps config source ids -> Source classes

  player/
    base.py         # Player ABC
    mpv.py, vlc.py  # Subprocess backends (headers, subtitles, resume)
    registry.py     # Maps config backend id -> Player

  ui/
    app.py                  # Textual App
    screens/main.py         # Search / Continue Watching / Library tabs
    screens/episodes.py     # Episode picker modal
    screens/quality.py      # Quality/stream picker modal
    widgets/                # Empty — drop in things like poster-art rendering later
```

## The `stremio` source (movies / series / anime via Torrentio)

Standard Stremio pattern, split in two:

* **Catalogue:** [Cinemeta](https://v3-cinemeta.strem.io/manifest.json)
  (`/catalog/{movie,series}/top/search=...` + `/meta/...` for episodes).
  Anime is classified from genres and behaves like series (episode picker).
* **Streams:** [Torrentio](https://torrentio.strem.fun/configure)
  (`/stream/{movie,series}/{imdbVideoId}.json`). Any compatible addon URL
  works (MediaFusion, Knightcrawler, self-hosted Torrentio).

Setup:

1. Enable it (default): `sources.enabled = ["stremio", "local"]` in
   `~/.config/stream-tui/config.toml`.
2. Optional but recommended: open
   `https://torrentio.strem.fun/configure`, pick providers, add your
   RealDebrid/AllDebrid/Premiumize key for **direct http links**, and paste
   the resulting configured URL as `sources.stremio.stream_url`
   (or `STREAM_TUI_STREAM_URL`). Without a debrid key you get
   `magnet:` links instead.
3. For magnets, install a local torrent streamer so mpv/vlc can play them:
   `npm install -g webtorrent-cli` (provides `webtorrent --mpv/--vlc`),
   or `peerflix`. Direct http links need nothing extra.

Env overrides: `STREAM_TUI_CINEMETA_URL`, `STREAM_TUI_STREAM_URL`
(`STREAM_TUI_TORRENTIO_URL` also accepted), `STREAM_TUI_TIMEOUT`.

Notes: Torrentio Cloudflare-blocks some datacenter/VPN IPs (HTTP 403).
On a blocked network the app shows a hint — use a residential IP,
self-host Torrentio, or swap `stream_url` for a compatible addon.

## Adding another source

1. Copy `stream_tui/sources/example.py` to e.g. `stream_tui/sources/myscraper.py`
   and implement `search()`, optionally `get_episodes()`, and `get_streams()`.
   Return `StreamLink`s with any `headers` (Referer/User-Agent/cookies) the
   CDN needs — the player backends forward those automatically.
2. Register it in `stream_tui/sources/registry.py`:
   ```python
   from stream_tui.sources.myscraper import MyScraperSource
   _AVAILABLE["myscraper"] = MyScraperSource
   ```
3. Add `"myscraper"` to `sources.enabled` in
   `~/.config/stream-tui/config.toml` (created on first run).

The rest of the app — search UI, episode/quality modals, playback, history,
downloads — needs no changes; it only ever talks to the `Source`/`StreamLink`
abstractions in `models.py` and `sources/base.py`.

## Sources & legal note

Ships with `local` (your own files) and `stremio` (Cinemeta metadata +
user-configured Stremio stream addon). Only point a source at content you
actually have the right to access and relay through your player (an API
you're licensed for, your own media, sites whose terms permit this kind
of automated/programmatic access, etc). Torrentio-style addons scrape
third-party torrents — fetching infringing copies through them may violate
copyright law. That decision, and any debrid keys / self-hosting, is left
entirely to you.

## Running

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/stream-tui
```

## Install worldwide (pip / GitHub / PyPI)

Anyone with Python 3.10+ can install it:

```
pip install stream-tui            # once published to PyPI
# or straight from git:
pip install git+https://github.com/<you>/stream-tui.git
```

To publish a release:

```
.venv/bin/python -m build
.venv/bin/python -m twine upload dist/*
```

Create the GitHub repo, push, and tag:

```
git init 2>/dev/null; git add -A; git commit -m "stremio source + publish-ready"
gh repo create <you>/stream-tui --public --source=. --push
git tag v0.2.0 && git push --tags
```

By default the `local` source indexes `~/Videos` (override with
`STREAM_TUI_LOCAL_DIR`). Playback requires `mpv` (or `vlc`) on PATH;
downloads require `yt-dlp`.

Config lives at `~/.config/stream-tui/config.toml`, data (history/library)
at `~/.local/share/stream-tui/`.

## Tests

```
.venv/bin/pytest
```
