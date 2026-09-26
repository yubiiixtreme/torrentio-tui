"""Config + on-disk paths (XDG-friendly), following the ani-cli/MovieBox-TUI
pattern of "sane defaults, everything overridable by a config file or env var".
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

APP_NAME = "torrentio-tui"

DEFAULT_CONFIG_TOML = """\
# torrentio-tui config
# Uncomment / edit as needed. Env vars (TORRENTIO_TUI_*) always win over this file.

[player]
backend = "mpv"          # mpv | vlc
default_quality = "1080p"

[sources]
# Order controls search fan-out / result ranking.
# "stremio" = Cinemeta catalogue (movie/series/anime search) + Torrentio-style
# streams, playable in mpv/vlc on the user's own machine.
enabled = ["stremio", "local"]

[sources.stremio]
# Metadata catalogue (search + episodes). Default is the public Cinemeta.
cinemeta_url = "https://v3-cinemeta.strem.io"
# Stream addon speaking Stremio's /stream/{type}/{id}.json protocol.
# Paste your *configured* URL from https://torrentio.strem.fun/configure
# (it embeds providers + optional RealDebrid/AllDebrid key for direct links),
# or a compatible alternative (MediaFusion / Knightcrawler / self-hosted).
# Env override: TORRENTIO_TUI_STREAM_URL.
stream_url = "https://torrentio.strem.fun"
# Env override: TORRENTIO_TUI_TIMEOUT (seconds).
timeout_seconds = 15.0

[downloads]
directory = "~/Videos/torrentio-tui"
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
    backend: str = "mpv"
    default_quality: str = "1080p"


@dataclass(slots=True)
class DownloadConfig:
    directory: Path = field(default_factory=lambda: Path("~/Videos/torrentio-tui").expanduser())


@dataclass(slots=True)
class StremioConfig:
    cinemeta_url: str = "https://v3-cinemeta.strem.io"
    stream_url: str = "https://torrentio.strem.fun"
    timeout_seconds: float = 15.0


@dataclass(slots=True)
class Config:
    player: PlayerConfig = field(default_factory=PlayerConfig)
    enabled_sources: list[str] = field(default_factory=lambda: ["stremio", "local"])
    stremio: StremioConfig = field(default_factory=StremioConfig)
    downloads: DownloadConfig = field(default_factory=DownloadConfig)

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

            cfg.enabled_sources = data.get("sources", {}).get("enabled", cfg.enabled_sources)

            stremio_cfg = data.get("sources", {}).get("stremio", {})
            if "cinemeta_url" in stremio_cfg:
                cfg.stremio.cinemeta_url = str(stremio_cfg["cinemeta_url"])
            if "stream_url" in stremio_cfg:
                cfg.stremio.stream_url = str(stremio_cfg["stream_url"])
            if "timeout_seconds" in stremio_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.stremio.timeout_seconds = float(stremio_cfg["timeout_seconds"])

            downloads = data.get("downloads", {})
            if "directory" in downloads:
                cfg.downloads.directory = Path(downloads["directory"]).expanduser()

        # Env vars always win (also honoured inside StremioSource itself).
        if env_cinemeta := os.environ.get("TORRENTIO_TUI_CINEMETA_URL"):
            cfg.stremio.cinemeta_url = env_cinemeta
        if env_stream := os.environ.get("TORRENTIO_TUI_STREAM_URL"):
            cfg.stremio.stream_url = env_stream
        if env_timeout := os.environ.get("TORRENTIO_TUI_TIMEOUT"):
            with contextlib.suppress(ValueError):
                cfg.stremio.timeout_seconds = float(env_timeout)
        if env_dir := os.environ.get("TORRENTIO_TUI_DOWNLOAD_DIR"):
            cfg.downloads.directory = Path(env_dir).expanduser()

        return cfg


def ensure_dirs() -> None:
    for d in (config_dir(), data_dir(), cache_dir()):
        d.mkdir(parents=True, exist_ok=True)

    cfg_path = config_file()
    if not cfg_path.exists():
        cfg_path.write_text(DEFAULT_CONFIG_TOML)
