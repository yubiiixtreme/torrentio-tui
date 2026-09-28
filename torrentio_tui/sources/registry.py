"""Wires source ids (from config) to `Source` instances.

Add your own source here once it's implemented:

    from torrentio_tui.sources.mysource import MySource
    _AVAILABLE["mysource"] = MySource
"""

from __future__ import annotations

from torrentio_tui.config import Config
from torrentio_tui.sources.adult import (
    HanimeSource,
    NHentaiSource,
    Rule34Source,
    StremioAdultSource,
)
from torrentio_tui.sources.anime import AnilistSource, NyaaSource, SubsPleaseSource
from torrentio_tui.sources.base import Source
from torrentio_tui.sources.free import (
    CometSource,
    DebridMediaManagerSource,
    EZTVSource,
    HorribleSubsSource,
    One337xSource,
    OpenSubtitlesSource,
    RARBGSource,
    SubsceneSource,
    YTSSource,
)
from torrentio_tui.sources.iptv import IPTVSource
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.sources.stremio import StremioSource

_AVAILABLE: dict[str, type[Source]] = {
    "local": LocalSource,
    "stremio": StremioSource,
    "mediafusion": StremioSource,
    "knightcrawler": StremioSource,
    "torrentio-selfhost": StremioSource,
    "comet": CometSource,
    "debridmediamanager": DebridMediaManagerSource,
    "yts": YTSSource,
    "eztv": EZTVSource,
    "rarbg": RARBGSource,
    "1337x": One337xSource,
    "horriblesubs": HorribleSubsSource,
    "subscene": SubsceneSource,
    "opensubtitles": OpenSubtitlesSource,
    "iptv": IPTVSource,
    "anilist": AnilistSource,
    "nyaa": NyaaSource,
    "subsplease": SubsPleaseSource,
    "stremio-adult": StremioAdultSource,
    "hanime": HanimeSource,
    "nhentai": NHentaiSource,
    "rule34": Rule34Source,
}


def load_sources(config: Config) -> list[Source]:
    sources = []
    for source_id in config.enabled_sources:
        cls = _AVAILABLE.get(source_id)
        if cls is None:
            continue
        if issubclass(cls, StremioSource):
            # Every Stremio-protocol addon (stremio, mediafusion,
            # knightcrawler, torrentio-selfhost, comet, debridmediamanager,
            # ...) shares this branch so per-source [sources.<id>] config
            # and the global proxy are honoured instead of silently
            # falling back to hardcoded defaults.
            source_cfg = config.sources_config.get(source_id, {})
            cinemeta_url = source_cfg.get("cinemeta_url")
            stream_url = source_cfg.get("stream_url")
            timeout = source_cfg.get("timeout_seconds", config.stremio.timeout_seconds)

            # Fall back to main stremio config if not specified
            if not cinemeta_url:
                cinemeta_url = config.stremio.cinemeta_url
            if not stream_url:
                # Use defaults for known alternative addons
                if source_id == "mediafusion":
                    stream_url = "https://mediafusion.elfhosted.com"
                elif source_id == "knightcrawler":
                    stream_url = "https://knightcrawler.ml"
                elif source_id == "torrentio-selfhost":
                    stream_url = "http://localhost:7000"
                elif source_id == "comet":
                    stream_url = "https://comet.strem.io"
                elif source_id == "debridmediamanager":
                    stream_url = "https://debridmediamanager.com"
                else:
                    stream_url = config.stremio.stream_url

            sources.append(
                cls(
                    cinemeta_url=cinemeta_url,
                    stream_url=stream_url,
                    timeout=timeout,
                    proxy_url=config.network.proxy_url,
                    source_id=source_id,
                )
            )
        elif cls is IPTVSource:
            # Get IPTV config
            iptv_cfg = config.sources_config.get("iptv", {})
            m3u_url = iptv_cfg.get("m3u_url") or config.iptv.m3u_url
            m3u_path = iptv_cfg.get("m3u_path") or config.iptv.m3u_path
            timeout = iptv_cfg.get("timeout_seconds", config.iptv.timeout_seconds)
            sources.append(cls(m3u_url=m3u_url, m3u_path=m3u_path, timeout=timeout))
        elif cls is AnilistSource:
            anilist_cfg = config.sources_config.get("anilist", {})
            include_adult = anilist_cfg.get("include_adult", False)
            sources.append(cls(include_adult=include_adult))
        elif cls in (StremioAdultSource, HanimeSource, NHentaiSource, Rule34Source):
            # Adult sources need the full config for age gating
            sources.append(cls(config=config))
        else:
            sources.append(cls())
    return sources


def available_source_ids() -> list[str]:
    return list(_AVAILABLE.keys())
