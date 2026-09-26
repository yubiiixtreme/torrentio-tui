"""Config + on-disk paths (XDG-friendly), following the ani-cli/MovieBox-TUI
pattern of "sane defaults, everything overridable by a config file or env var".
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # stdlib tomllib only exists from 3.11 onward

from torrentio_tui.termux import is_termux

APP_NAME = "torrentio-tui"


def _default_player_backend() -> str:
    return "termux" if is_termux() else "mpv"


#: Curated theme list, cycled with the "t" key. "torrentio" is our own;
#: the rest ship built into Textual — no extra registration needed.
THEMES: tuple[str, ...] = (
    "torrentio",
    "dracula",
    "nord",
    "gruvbox",
    "catppuccin-mocha",
    "tokyo-night",
    "monokai",
)


def _default_hwdec() -> str:
    # mpv's own recommended safe default: enables hardware decoding where
    # supported, silently falls back to software otherwise. Most useful on
    # Android (Termux + the `mpv`/`vlc-android` backends), but harmless
    # anywhere mpv runs, so it's the default everywhere.
    return "auto-safe"


def _default_config_toml() -> str:
    return f"""\
# torrentio-tui config
# Uncomment / edit as needed. Env vars (TORRENTIO_TUI_*) always win over this file.

[player]
backend = "{_default_player_backend()}"          # mpv | vlc | termux | vlc-android
default_quality = "1080p"
# Hardware decoding for mpv (ignored by other backends). "auto-safe" is
# mpv's own recommended default — cleanly falls back to software decoding
# where unsupported. Set to "" to disable, or "auto" for a more aggressive
# (occasionally unstable) mode. Most impactful on Android/Termux.
hwdec = "{_default_hwdec()}"

[ui]
# One of: {", ".join(THEMES)}
# Press "t" in-app to cycle through them (saved back here automatically),
# or Ctrl+P → "theme" for the full Textual theme list.
theme = "torrentio"

[sources]
# Order controls search fan-out / result ranking.
# "stremio" = Cinemeta catalogue (movie/series/anime search) + Torrentio-style
# streams, playable in mpv/vlc on the user's own machine.
# "local" = local video files (indexes ~/Videos by default).
# "mediafusion" = MediaFusion addon (https://mediafusion.elfhosted.com)
# "knightcrawler" = Knightcrawler addon (https://knightcrawler.ml)
# "torrentio-selfhost" = Self-hosted Torrentio instance
# "iptv" = Live TV channels from M3U playlist
# "anilist" = Anime metadata from AniList
# "nyaa" = Anime torrents from Nyaa.si
# "subsplease" = Latest anime from SubsPlease
# "stremio-adult" = Adult content via Stremio (requires [adult] enabled)
# "hanime" = Hentai anime from Hanime.tv (requires [adult] enabled)
enabled = ["stremio", "mediafusion", "local"]

[sources.stremio]
# Metadata catalogue (search + episodes). Default is the public Cinemeta.
cinemeta_url = "https://v3-cinemeta.strem.io"
# Stream addon speaking Stremio's /stream/{{type}}/{{id}}.json protocol.
# Paste your *configured* URL from https://torrentio.strem.fun/configure
# (it embeds providers + optional RealDebrid/AllDebrid key for direct links),
# or a compatible alternative (MediaFusion / Knightcrawler / self-hosted).
# Env override: TORRENTIO_TUI_STREAM_URL.
stream_url = "https://torrentio.strem.fun"
# Env override: TORRENTIO_TUI_TIMEOUT (seconds).
timeout_seconds = 15.0

# --- Alternative stream addons (enabled by default alongside Torrentio, so
#     one being blocked/down doesn't leave you with zero results — remove
#     from [sources].enabled above to turn any of these off) ---
[sources.mediafusion]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://mediafusion.elfhosted.com"
timeout_seconds = 15.0

# [sources.knightcrawler]
# cinemeta_url = "https://v3-cinemeta.strem.io"
# stream_url = "https://knightcrawler.ml"
# timeout_seconds = 15.0
#
# [sources.torrentio-selfhost]
# cinemeta_url = "https://v3-cinemeta.strem.io"
# stream_url = "http://localhost:7000"
# timeout_seconds = 15.0

# --- IPTV / Live TV ---
# [sources.iptv]
# m3u_url = "https://example.com/playlist.m3u"  # or local file path
# m3u_path = "~/Videos/iptv.m3u"
# timeout_seconds = 15.0

# --- Anime-specific sources ---
# [sources.anilist]
# include_adult = false
#
# [sources.nyaa]
#
# [sources.subsplease]

# --- Adult content (opt-in, requires [adult] enabled = true) ---
# [sources.stremio-adult]
# cinemeta_url = "https://v3-cinemeta.strem.io"
# stream_url = "https://torrentio.strem.fun"
# timeout_seconds = 15.0
#
# [sources.hanime]

[network]
# Route requests through a proxy — useful if Torrentio Cloudflare-blocks
# your IP (HTTP 403). Cloudflare WARP's local proxy mode is a common fix:
#   warp-cli mode proxy && warp-cli connect   # starts a SOCKS5 proxy on :40000
# socks5:// needs `pip install pysocks` (or install as torrentio-tui[proxy]).
# Env override: TORRENTIO_TUI_PROXY.
# proxy_url = "socks5://127.0.0.1:40000"

[downloads]
directory = "~/Videos/torrentio-tui"

[adult]
# Enable adult content sources (stremio-adult, hanime)
# ONLY enable if you are of legal age in your jurisdiction!
enabled = false
"""


def _xdg_path(env_var: str, fallback: str) -> Path:
    return Path(os.environ.get(env_var, fallback)).expanduser()


def config_dir() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", "~/.config") / APP_NAME


def data_dir() -> Path:
    return _xdg_path("XDG_DATA_HOME", "~/.local/share") / APP_NAME


def cache_dir() -> Path:
    return _xdg_path("XDG_CACHE_HOME", "~/.cache") / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.toml"


def history_file() -> Path:
    return data_dir() / "history.json"


def library_file() -> Path:
    return data_dir() / "library.json"


@dataclass(slots=True)
class PlayerConfig:
    backend: str = field(default_factory=_default_player_backend)
    default_quality: str = "1080p"
    hwdec: str = field(default_factory=_default_hwdec)


@dataclass(slots=True)
class DownloadConfig:
    directory: Path = field(default_factory=lambda: Path("~/Videos/torrentio-tui").expanduser())


@dataclass(slots=True)
class StremioConfig:
    cinemeta_url: str = "https://v3-cinemeta.strem.io"
    stream_url: str = "https://torrentio.strem.fun"
    timeout_seconds: float = 15.0


@dataclass(slots=True)
class IPTVConfig:
    m3u_url: str | None = None
    m3u_path: str | None = None
    timeout_seconds: float = 15.0


@dataclass(slots=True)
class AdultConfig:
    enabled: bool = False


@dataclass(slots=True)
class NetworkConfig:
    proxy_url: str | None = None


@dataclass(slots=True)
class UIConfig:
    theme: str = "torrentio"


@dataclass(slots=True)
class Config:
    player: PlayerConfig = field(default_factory=PlayerConfig)
    enabled_sources: list[str] = field(default_factory=lambda: ["stremio", "local"])
    stremio: StremioConfig = field(default_factory=StremioConfig)
    iptv: IPTVConfig = field(default_factory=IPTVConfig)
    adult: AdultConfig = field(default_factory=AdultConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    downloads: DownloadConfig = field(default_factory=DownloadConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    sources_config: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        path = config_file()
        if path.exists():
            data = tomllib.loads(path.read_text())
            player = data.get("player", {})
            cfg.player.backend = os.environ.get(
                "TORRENTIO_TUI_PLAYER", player.get("backend", cfg.player.backend)
            )
            cfg.player.default_quality = player.get("default_quality", cfg.player.default_quality)
            cfg.player.hwdec = player.get("hwdec", cfg.player.hwdec)

            cfg.enabled_sources = data.get("sources", {}).get("enabled", cfg.enabled_sources)

            # Parse all source configs under [sources.*]
            sources_data = data.get("sources", {})
            for key, value in sources_data.items():
                if key != "enabled" and isinstance(value, dict):
                    cfg.sources_config[key] = value

            stremio_cfg = sources_data.get("stremio", {})
            if "cinemeta_url" in stremio_cfg:
                cfg.stremio.cinemeta_url = str(stremio_cfg["cinemeta_url"])
            if "stream_url" in stremio_cfg:
                cfg.stremio.stream_url = str(stremio_cfg["stream_url"])
            if "timeout_seconds" in stremio_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.stremio.timeout_seconds = float(stremio_cfg["timeout_seconds"])

            # Parse IPTV config
            iptv_cfg = sources_data.get("iptv", {})
            if "m3u_url" in iptv_cfg:
                cfg.iptv.m3u_url = str(iptv_cfg["m3u_url"])
            if "m3u_path" in iptv_cfg:
                cfg.iptv.m3u_path = str(iptv_cfg["m3u_path"])
            if "timeout_seconds" in iptv_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.iptv.timeout_seconds = float(iptv_cfg["timeout_seconds"])

            # Parse adult config
            adult_cfg = data.get("adult", {})
            if "enabled" in adult_cfg:
                cfg.adult.enabled = bool(adult_cfg["enabled"])

            network_cfg = data.get("network", {})
            if network_cfg.get("proxy_url"):
                cfg.network.proxy_url = str(network_cfg["proxy_url"])

            downloads = data.get("downloads", {})
            if "directory" in downloads:
                cfg.downloads.directory = Path(downloads["directory"]).expanduser()

            ui_cfg = data.get("ui", {})
            if "theme" in ui_cfg:
                cfg.ui.theme = str(ui_cfg["theme"])

        # Env vars always win (also honoured inside StremioSource itself).
        if env_cinemeta := os.environ.get("TORRENTIO_TUI_CINEMETA_URL"):
            cfg.stremio.cinemeta_url = env_cinemeta
        if env_stream := os.environ.get("TORRENTIO_TUI_STREAM_URL"):
            cfg.stremio.stream_url = env_stream
        if env_timeout := os.environ.get("TORRENTIO_TUI_TIMEOUT"):
            with contextlib.suppress(ValueError):
                cfg.stremio.timeout_seconds = float(env_timeout)
        if env_proxy := os.environ.get("TORRENTIO_TUI_PROXY"):
            cfg.network.proxy_url = env_proxy
        if (env_hwdec := os.environ.get("TORRENTIO_TUI_HWDEC")) is not None:
            cfg.player.hwdec = env_hwdec
        if env_dir := os.environ.get("TORRENTIO_TUI_DOWNLOAD_DIR"):
            cfg.downloads.directory = Path(env_dir).expanduser()
        if env_adult := os.environ.get("TORRENTIO_TUI_ADULT"):
            cfg.adult.enabled = env_adult.lower() in ("1", "true", "yes", "on")
        if env_theme := os.environ.get("TORRENTIO_TUI_THEME"):
            cfg.ui.theme = env_theme

        return cfg


def save_theme(theme: str) -> None:
    """Best-effort persistence for the "t" theme-cycle keybinding: patches
    just the `theme = "..."` line under `[ui]` in the existing config.toml,
    leaving everything else (including the user's own comments) untouched.
    Silently does nothing if the file or that line isn't there — cycling
    still works for the rest of the session either way, it just won't be
    remembered next launch.
    """
    import re

    path = config_file()
    if not path.exists():
        return
    text = path.read_text()
    new_text, count = re.subn(
        r'^theme = ".*"$', f'theme = "{theme}"', text, count=1, flags=re.MULTILINE
    )
    if count:
        path.write_text(new_text)


def ensure_dirs() -> None:
    for d in (config_dir(), data_dir(), cache_dir()):
        d.mkdir(parents=True, exist_ok=True)

    cfg_path = config_file()
    if not cfg_path.exists():
        cfg_path.write_text(_default_config_toml())
