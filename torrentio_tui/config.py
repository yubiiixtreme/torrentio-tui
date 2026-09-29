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

from torrentio_tui.languages import LanguageConfig
from torrentio_tui.termux import is_termux

APP_NAME = "torrentio-tui"


def _default_player_backend() -> str:
    return "termux" if is_termux() else "mpv"


#: Curated theme list, cycled with the "t" key. "torrentio" and
#: "oled-black" are ours (registered in ui/app.py); the rest ship built
#: into Textual — no extra registration needed. Any theme file dropped
#: into ~/.config/torrentio-tui/themes/ (see torrentio_tui/themes.py) is
#: appended to the cycle automatically and is always reachable via the
#: command palette (Ctrl+P -> "theme"), curated list or not.
THEMES: tuple[str, ...] = (
    "torrentio",
    "oled-black",
    "matrix",
    "void",
    "synthwave",
    "amber",
    "dracula",
    "nord",
    "gruvbox",
    "catppuccin-mocha",
    "catppuccin-latte",
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
# Live in-app HUD (buffer health, cache speed) instead of handing mpv the
# whole terminal. mpv still needs its own GUI window (X11/Wayland/macOS/
# Windows) for video output -- leave this off on a terminal-only/headless
# setup. Ignored by backends other than mpv, and by magnet/torrent streams.
hud = false

[ui]
# One of: {", ".join(THEMES)}
# Press "t" in-app to cycle through them (saved back here automatically),
# or Ctrl+P -> "theme" for the full Textual theme list.
theme = "torrentio"

[sources]
# Order controls search fan-out / result ranking. Sources are grouped by
# category (`torrentio-tui --list-sources` shows the same grouping):
#
# [streams]  playable movies/series. "stremio" = Cinemeta catalogue +
#   Torrentio-style streams. "mediafusion"/"comet" = alternative addons
#   enabled by default so one being blocked/down never leaves you with
#   zero results. "aiostreams" = super-addon merging 80+ community
#   addons (paste your configured URL). "stremthru" = your debrid-store
#   catalog (needs store token in the configured URL). "jackettio" =
#   Jackett trackers via debrid. "deflix"/"stremify"/"torrentio-selfhost" =
#   self-hosted addons (run locally, point stream_url at them).
#   "yts" = YTS/YIFY movie torrents (official API, magnets).
#   "knightcrawler" = deprecated (project ceased 2024, public instance
#   retired) — kept for old configs, not recommended.
# [catalogue]  metadata companions (free, keyless). "tvmaze" = series
#   air-dates/episodes (streams bridged via IMDb id). "jikan" =
#   MyAnimeList anime data. "kitsu" = Kitsu anime data. "anilist" =
#   AniList anime data. Catalogue results resolve playback through your
#   configured stream addon by title/IMDb match.
# [anime]  "nyaa" = anime torrents from Nyaa.si. "subsplease" = latest
#   anime releases from SubsPlease.
# [live]  "iptv" = Live TV channels from an M3U playlist.
# [local]  "local" = your own video files (indexes ~/Videos by default).
# [adult]  opt-in, requires [adult] enabled = true below:
#   "stremio-adult", "hanime", "nhentai", "rule34".
enabled = ["stremio", "mediafusion", "comet", "local"]

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
#     one being blocked/down doesn't leave you with zero results -- remove
#     from [sources].enabled above to turn any of these off) ---
[sources.mediafusion]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://mediafusion.elfhosted.com"
timeout_seconds = 15.0

[sources.comet]
cinemeta_url = "https://v3-cinemeta.strem.io"
stream_url = "https://comet.elfhosted.com"
timeout_seconds = 15.0

    # --- More stream addons (opt-in: add the id to [sources].enabled) ---
    # [sources.aiostreams]
    # # Paste your *configured* URL from https://aiostreams.elfhosted.com/stremio/configure
    # # (embeds your addons + debrid keys); the bare public instance is limited.
    # stream_url = "https://aiostreams.elfhosted.com"
    # timeout_seconds = 15.0
    #
    # [sources.stremthru]
    # # Paste your configured Store URL from https://stremthru.elfhosted.com/stremio
    # # (embeds your debrid-store token).
    # stream_url = "https://stremthru.elfhosted.com/stremio/store"
    # timeout_seconds = 15.0
    #
    # [sources.jackettio]
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "https://jackettio.elfhosted.com"
    # timeout_seconds = 15.0
    #
    # [sources.deflix]
    # # Self-hosted: run deflix-stremio, open http://localhost:8080/configure.
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "http://localhost:8080"
    # timeout_seconds = 15.0
    #
    # [sources.stremify]
    # # Self-hosted: run stremify, point at your instance.
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "http://localhost:3000"
    # timeout_seconds = 15.0
    #
    # [sources.knightcrawler]
    # # DEPRECATED: project ceased development in 2024 and the public instance
    # # was retired. Kept so old configs still load; prefer comet/mediafusion.
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "https://knightcrawler.elfhosted.com"
    # timeout_seconds = 15.0
    #
    # [sources.torrentio-selfhost]
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "http://localhost:7000"
    # timeout_seconds = 15.0
    #
    # [sources.stremio-community]
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "https://stremio-community.github.io"
    # timeout_seconds = 15.0
    #
    # [sources.superstream]
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "https://superstream.strem.io"
    # timeout_seconds = 15.0
    #
    # [sources.torrentio-cloud]
    # cinemeta_url = "https://v3-cinemeta.strem.io"
    # stream_url = "https://torrentio-cloud.strem.fun"
    # timeout_seconds = 15.0
    #
    # --- Torrent-index sources (real APIs, magnets play via the torrent bridge) ---
    # [sources.yts]
    # api_url = "https://movies-api.accel.li/api/v2"
    # timeout_seconds = 15.0
    #
    # [sources.eztv]
    # timeout_seconds = 15.0
    #
    # [sources.torrentgalaxy]
    # timeout_seconds = 15.0
    #
    # [sources.magnetdl]
    # timeout_seconds = 15.0
    #
    # [sources.vumoo]
    # timeout_seconds = 15.0
    #
    # [sources.solarmovie]
    # timeout_seconds = 15.0
#
# --- Catalogue companions (free, keyless; playback bridges through your
#     configured stream addon, so a debrid URL helps these too) ---
# [sources.tvmaze]
# # api_url = "https://api.tvmaze.com"
# # stream_url = "https://torrentio.strem.fun"  # addon used for playback
# # timeout_seconds = 15.0
#
# [sources.jikan]
# # api_url = "https://api.jikan.moe/v4"
# # stream_url = "https://torrentio.strem.fun"
# # timeout_seconds = 15.0
#
# [sources.kitsu]
# # api_url = "https://kitsu.io/api/edge"
# # stream_url = "https://torrentio.strem.fun"
# # timeout_seconds = 15.0

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
#
# [sources.nhentai]
#
# [sources.rule34]

[network]
# Route requests through a proxy — useful if Torrentio Cloudflare-blocks
# your IP (HTTP 403). Cloudflare WARP's local proxy mode is a common fix:
#   warp-cli mode proxy && warp-cli connect   # starts a SOCKS5 proxy on :40000
# socks5:// needs `pip install pysocks` (or install as torrentio-tui[proxy]).
# Env override: TORRENTIO_TUI_PROXY.
# proxy_url = "socks5://127.0.0.1:40000"

[subtitles]
# Auto-attach subtitles at playback time. When a picked stream has no
# subtitle of its own, the enabled providers are queried (in order) and
# the best preferred-language match is downloaded to the cache and passed
# to mpv/vlc. Providers that aren't configured are skipped quietly, so
# subtitles can never break playback. Preferred languages come from
# [language] subtitle_languages. Env override: TORRENTIO_TUI_SUBTITLES=1.
enabled = false
providers = ["subdb", "opensubtitles"]
timeout_seconds = 15.0
# OpenSubtitles.com: free API key from https://www.opensubtitles.com
# (needed for search; env TORRENTIO_TUI_OS_API_KEY). Downloads also need
# a username+password (env TORRENTIO_TUI_OS_USERNAME/_PASSWORD).
# opensubtitles_api_key = ""
# opensubtitles_username = ""
# opensubtitles_password = ""

[downloads]
directory = "~/Videos/torrentio-tui"

[adult]
# Enable adult content sources (stremio-adult, hanime, nhentai, rule34)
# ONLY enable if you are of legal age in your jurisdiction!
enabled = false

[language]
# UI language (ISO 639-1 code): en, es, fr, de, it, pt, ru, zh, ja, ko, etc.
ui_language = "en"
# Preferred subtitle languages (in order of preference, ISO 639-2/T codes)
subtitle_languages = ["eng", "spa", "fre"]
# Preferred audio languages (in order of preference)
audio_languages = ["eng", "jpn", "kor"]
# Auto-translate subtitles if preferred language not available
auto_translate = true
# Prefer original audio with subtitles
prefer_original_audio = true
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
    hud: bool = False


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
class SubtitlesConfig:
    """Auto-subtitle providers for playback. Off by default; when enabled,
    streams without their own subtitle get the best preferred-language
    match attached (downloaded to the cache, so mpv/vlc always get a
    local file). Providers that aren't configured are skipped quietly."""

    enabled: bool = False
    providers: list[str] = field(default_factory=lambda: ["subdb", "opensubtitles"])
    timeout_seconds: float = 15.0
    # OpenSubtitles.com: free API key from opensubtitles.com (needed for
    # search); username+password additionally needed for downloads.
    # Env overrides: TORRENTIO_TUI_OS_API_KEY / _OS_USERNAME / _OS_PASSWORD.
    opensubtitles_api_key: str | None = None
    opensubtitles_username: str | None = None
    opensubtitles_password: str | None = None


@dataclass(slots=True)
class UIConfig:
    theme: str = "torrentio"


@dataclass(slots=True)
class Config:
    player: PlayerConfig = field(default_factory=PlayerConfig)
    enabled_sources: list[str] = field(
        default_factory=lambda: ["stremio", "mediafusion", "comet", "local"]
    )
    stremio: StremioConfig = field(default_factory=StremioConfig)
    iptv: IPTVConfig = field(default_factory=IPTVConfig)
    adult: AdultConfig = field(default_factory=AdultConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    subtitles: SubtitlesConfig = field(default_factory=SubtitlesConfig)
    downloads: DownloadConfig = field(default_factory=DownloadConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    # NB: default_factory=LanguageConfig (not a shared DEFAULT instance) —
    # each Config gets its own copy so in-memory tweaks (e.g. the subtitle
    # picker reordering preferences) never leak across Config instances.
    language: LanguageConfig = field(default_factory=LanguageConfig)
    sources_config: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        path = config_file()
        if path.exists():
            try:
                data = tomllib.loads(path.read_text())
            except (OSError, UnicodeDecodeError, ValueError):
                # Malformed config must never kill startup — fall back to
                # defaults (env vars below still apply).
                data = {}
            if not isinstance(data, dict):
                data = {}
            player = data.get("player", {})
            if not isinstance(player, dict):
                player = {}
            cfg.player.backend = os.environ.get(
                "TORRENTIO_TUI_PLAYER", player.get("backend", cfg.player.backend)
            )
            cfg.player.default_quality = player.get("default_quality", cfg.player.default_quality)
            cfg.player.hwdec = player.get("hwdec", cfg.player.hwdec)
            cfg.player.hud = bool(player.get("hud", cfg.player.hud))

            enabled = data.get("sources", {}).get("enabled", cfg.enabled_sources)
            # A bare string ("stremio") would otherwise iterate char by
            # char downstream — accept it as a single source, drop garbage.
            if isinstance(enabled, str):
                enabled = [enabled]
            if isinstance(enabled, list):
                cfg.enabled_sources = [str(s) for s in enabled if isinstance(s, str)]

            # Parse all source configs under [sources.*]
            sources_data = data.get("sources", {})
            if not isinstance(sources_data, dict):
                sources_data = {}
            for key, value in sources_data.items():
                if key != "enabled" and isinstance(value, dict):
                    cfg.sources_config[key] = value

            stremio_cfg = sources_data.get("stremio", {})
            if not isinstance(stremio_cfg, dict):
                stremio_cfg = {}
            if "cinemeta_url" in stremio_cfg:
                cfg.stremio.cinemeta_url = str(stremio_cfg["cinemeta_url"])
            if "stream_url" in stremio_cfg:
                cfg.stremio.stream_url = str(stremio_cfg["stream_url"])
            if "timeout_seconds" in stremio_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.stremio.timeout_seconds = float(stremio_cfg["timeout_seconds"])

            # Parse IPTV config
            iptv_cfg = sources_data.get("iptv", {})
            if not isinstance(iptv_cfg, dict):
                iptv_cfg = {}
            if "m3u_url" in iptv_cfg:
                cfg.iptv.m3u_url = str(iptv_cfg["m3u_url"])
            if "m3u_path" in iptv_cfg:
                cfg.iptv.m3u_path = str(iptv_cfg["m3u_path"])
            if "timeout_seconds" in iptv_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.iptv.timeout_seconds = float(iptv_cfg["timeout_seconds"])

            # Parse adult config
            adult_cfg = data.get("adult", {})
            if not isinstance(adult_cfg, dict):
                adult_cfg = {}
            if "enabled" in adult_cfg:
                cfg.adult.enabled = bool(adult_cfg["enabled"])

            network_cfg = data.get("network", {})
            if not isinstance(network_cfg, dict):
                network_cfg = {}
            if network_cfg.get("proxy_url"):
                cfg.network.proxy_url = str(network_cfg["proxy_url"])

            # Parse subtitles config
            sub_cfg = data.get("subtitles", {})
            if not isinstance(sub_cfg, dict):
                sub_cfg = {}
            if "enabled" in sub_cfg:
                cfg.subtitles.enabled = bool(sub_cfg["enabled"])
            if isinstance(sub_cfg.get("providers"), list):
                cfg.subtitles.providers = [
                    str(p) for p in sub_cfg["providers"] if isinstance(p, str)
                ]
            if "timeout_seconds" in sub_cfg:
                with contextlib.suppress(ValueError, TypeError):
                    cfg.subtitles.timeout_seconds = float(sub_cfg["timeout_seconds"])
            for key in (
                "opensubtitles_api_key",
                "opensubtitles_username",
                "opensubtitles_password",
            ):
                if sub_cfg.get(key):
                    setattr(cfg.subtitles, key, str(sub_cfg[key]))

            downloads = data.get("downloads", {})
            if not isinstance(downloads, dict):
                downloads = {}
            if "directory" in downloads:
                cfg.downloads.directory = Path(downloads["directory"]).expanduser()

            ui_cfg = data.get("ui", {})
            if not isinstance(ui_cfg, dict):
                ui_cfg = {}
            if "theme" in ui_cfg:
                cfg.ui.theme = str(ui_cfg["theme"])

            # Parse language config
            lang_cfg = data.get("language", {})
            if not isinstance(lang_cfg, dict):
                lang_cfg = {}
            if "ui_language" in lang_cfg:
                cfg.language.ui_language = str(lang_cfg["ui_language"])
            if "subtitle_languages" in lang_cfg:
                cfg.language.subtitle_languages = list(lang_cfg["subtitle_languages"])
            if "audio_languages" in lang_cfg:
                cfg.language.audio_languages = list(lang_cfg["audio_languages"])
            if "auto_translate" in lang_cfg:
                cfg.language.auto_translate = bool(lang_cfg["auto_translate"])
            if "prefer_original_audio" in lang_cfg:
                cfg.language.prefer_original_audio = bool(lang_cfg["prefer_original_audio"])

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
        if env_subs := os.environ.get("TORRENTIO_TUI_SUBTITLES"):
            cfg.subtitles.enabled = env_subs.lower() in ("1", "true", "yes", "on")
        if env_os_key := os.environ.get("TORRENTIO_TUI_OS_API_KEY"):
            cfg.subtitles.opensubtitles_api_key = env_os_key
        if env_os_user := os.environ.get("TORRENTIO_TUI_OS_USERNAME"):
            cfg.subtitles.opensubtitles_username = env_os_user
        if env_os_pass := os.environ.get("TORRENTIO_TUI_OS_PASSWORD"):
            cfg.subtitles.opensubtitles_password = env_os_pass
        if (env_hwdec := os.environ.get("TORRENTIO_TUI_HWDEC")) is not None:
            cfg.player.hwdec = env_hwdec
        if env_hud := os.environ.get("TORRENTIO_TUI_HUD"):
            cfg.player.hud = env_hud.lower() in ("1", "true", "yes", "on")
        if env_dir := os.environ.get("TORRENTIO_TUI_DOWNLOAD_DIR"):
            cfg.downloads.directory = Path(env_dir).expanduser()
        if env_adult := os.environ.get("TORRENTIO_TUI_ADULT"):
            cfg.adult.enabled = env_adult.lower() in ("1", "true", "yes", "on")
        if env_theme := os.environ.get("TORRENTIO_TUI_THEME"):
            cfg.ui.theme = env_theme
        if env_lang := os.environ.get("TORRENTIO_TUI_LANG"):
            cfg.language.ui_language = env_lang

        return cfg


def get_language_config() -> LanguageConfig:
    """Get the language configuration from the loaded config or defaults."""
    return Config.load().language


def save_theme(theme: str) -> None:
    """Best-effort persistence for the "t" theme-cycle keybinding: patches
    just the `theme = ...` line under `[ui]` in the existing config.toml,
    leaving everything else (including the user's own comments) untouched.
    Handles double- and single-quoted values, and appends a `[ui]` section
    if the file has none. Silently does nothing if the file isn't there —
    cycling still works for the rest of the session either way, it just
    won't be remembered next launch.
    """
    import re

    path = config_file()
    if not path.exists():
        return
    text = path.read_text()
    # Only patch a theme line that lives under the [ui] section (not e.g.
    # a similarly-named key under some other table).
    ui_match = re.search(r"^\[ui\][ \t]*$", text, flags=re.MULTILINE)
    if ui_match is None:
        text = text.rstrip("\n") + f'\n\n[ui]\ntheme = "{theme}"\n'
        ui_match = re.search(r"^\[ui\][ \t]*$", text, flags=re.MULTILINE)
        assert ui_match is not None
    section_start = ui_match.end()
    next_section = re.search(r"^\[", text[section_start:], flags=re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)
    section = text[section_start:section_end]
    new_section, count = re.subn(
        r"""^theme\s*=\s*["'].*["']\s*$""",
        f'theme = "{theme}"',
        section,
        count=1,
        flags=re.MULTILINE,
    )
    if count:
        new_text = text[:section_start] + new_section + text[section_end:]
    else:
        new_text = text[:section_end].rstrip("\n") + f'\ntheme = "{theme}"\n' + text[section_end:]
    # Ensure file ends with newline
    if not new_text.endswith("\n"):
        new_text += "\n"
    path.write_text(new_text)


def save_enabled_sources(enabled: list[str]) -> None:
    """Best-effort persistence for source toggles: patches just the
    `enabled = [...]` line under `[sources]` in config.toml, preserving
    comments. Silently does nothing if the file isn't there."""
    import re

    path = config_file()
    if not path.exists():
        return
    text = path.read_text()
    quoted = ", ".join(f'"{s}"' for s in enabled)
    replacement = f"enabled = [{quoted}]"
    sources_match = re.search(r"^\[sources\][ \t]*$", text, flags=re.MULTILINE)
    if sources_match is None:
        text = text.rstrip("\n") + f"\n\n[sources]\n{replacement}\n"
        path.write_text(text if text.endswith("\n") else text + "\n")
        return
    section_start = sources_match.end()
    next_section = re.search(r"^\[", text[section_start:], flags=re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)
    section = text[section_start:section_end]
    new_section, count = re.subn(
        r"""^enabled\s*=\s*\[.*\]\s*$""",
        replacement,
        section,
        count=1,
        flags=re.MULTILINE,
    )
    if count:
        new_text = text[:section_start] + new_section + text[section_end:]
    else:
        new_text = text[:section_end].rstrip("\n") + f"\n{replacement}\n" + text[section_end:]
    if not new_text.endswith("\n"):
        new_text += "\n"
    path.write_text(new_text)


def ensure_dirs() -> None:
    for d in (config_dir(), data_dir(), cache_dir()):
        d.mkdir(parents=True, exist_ok=True)

    cfg_path = config_file()
    if not cfg_path.exists():
        cfg_path.write_text(_default_config_toml())
