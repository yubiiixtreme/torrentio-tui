"""Wires source ids (from config) to `Source` instances.

Sources are grouped into categories (see `CATEGORIES`) surfaced by
`--list-sources`, the in-app help screen, and the config template:

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
from torrentio_tui.sources.adult_extended import (
    EHentaiSource,
    HentaiHavenSource,
    HitomiLaSource,
)
from torrentio_tui.sources.anime import AnilistSource, NyaaSource, SubsPleaseSource
from torrentio_tui.sources.anime_extended import (
    AniDexSource,
    AnimeToshoSource,
    TokyoToshokanSource,
)
from torrentio_tui.sources.base import Source
from torrentio_tui.sources.catalogues import (
    JikanSource,
    KitsuSource,
    TMDBSource,
    TraktSource,
    TVMazeSource,
)
from torrentio_tui.sources.extended import (
    EZTVRSSSource,
    MagnetDLSource,
    SolarMovieSource,
    StremioCommunitySource,
    StremioSuperStreamSource,
    StremioTorrentioCloudSource,
    TorrentGalaxySource,
    VumooSource,
)
from torrentio_tui.sources.free import (
    AIOStreamsSource,
    AniWorldSource,
    CometSource,
    DeflixSource,
    HorribleSubsSource,
    JackettioSource,
    NuvioStreamsSource,
    OtakuStreamSource,
    StremifySource,
    StremThruStoreSource,
)
from torrentio_tui.sources.iptv import IPTVOrgSource, IPTVSource
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.sources.rss_indexes import (
    GloDLSSource,
    LimeTorrentsSource,
    TorrentDownloadsSource,
)
from torrentio_tui.sources.stremio import StremioSource
from torrentio_tui.sources.torrent_extended import (
    NyaaTorrentsSource,
    RARBGMirrorSource,
    ThePirateBaySource,
)
from torrentio_tui.sources.torrentapi import (
    PirateBaySource,
    RARBGSource,
    Thirteen37xSource,
    YTSSource,
)

#: Friendly names for ids that share one class (plain `StremioSource`
#: instances get their real name only after construction with
#: `source_id=` — see `_stremio_kwargs`).
_SOURCE_DISPLAY_NAMES = {
    "stremio": "Stremio (Cinemeta + Torrentio)",
    "mediafusion": "MediaFusion",
    "knightcrawler": "Knightcrawler (deprecated)",
    "torrentio-selfhost": "Torrentio (self-hosted)",
    "1337x": "1337x (Torrent Index)",
    "piratebay": "The Pirate Bay",
    "tmdb": "TMDB (Movie/TV Catalogue)",
    "trakt": "Trakt (Trending/Personal)",
    "horriblesubs": "HorribleSubs (Legacy)",
    "aniworld": "AniWorld (German Anime)",
    "otakustream": "OtakuStream (Anime)",
    "eztv-rss": "EZTV (TV Series Torrents)",
    "torrentgalaxy": "TorrentGalaxy (Torrent Index)",
    "magnetdl": "MagnetDL (Magnet Search)",
    "vumoo": "Vumoo (Free Streaming)",
    "solarmovie": "SolarMovie (Free Streaming)",
    "stremio-community": "Stremio Community (Free Addon)",
    "superstream": "SuperStream (Free Addon)",
    "torrentio-cloud": "Torrentio Cloud (Free)",
    "limetorrents": "LimeTorrents (Torrent Index)",
    "torrentdownloads": "TorrentDownloads (Torrent Index)",
    "glodls": "GloDLS (Torrent Index)",
    "iptv-org": "IPTV-org (Free World TV)",
    "anidex": "AniDex (Anime Torrents)",
    "animetosho": "Anime Tosho (Anime Releases)",
    "tokyotoshokan": "Tokyo Toshokan (Anime Index)",
    "thepiratebay": "The Pirate Bay (API + RSS)",
    "rarbg-mirror": "RARBG Mirrors (torrentapi.org)",
    "nyaa-torrents": "Nyaa Torrents (Mirrors)",
    "ehentai": "E-Hentai (Adult)",
    "hitomila": "Hitomi.la (Adult)",
    "hentaihaven": "HentaiHaven (Adult)",
}


def describe_source(source_id: str) -> str:
    """Human-readable name for `source_id` (per-id override when several
    ids share one class, otherwise the class name)."""
    if source_id in _SOURCE_DISPLAY_NAMES:
        return _SOURCE_DISPLAY_NAMES[source_id]
    cls = _AVAILABLE.get(source_id)
    return cls.name if cls is not None else source_id


#: Category id -> (label, description), in display order.
CATEGORIES: dict[str, tuple[str, str]] = {
    "streams": ("Streams", "Playable movies & series (addons and torrent indexes)"),
    "catalogue": ("Catalogue", "Metadata companions — playback bridges via your stream addon"),
    "anime": ("Anime", "Anime torrents and trackers"),
    "live": ("Live TV", "Live channels from playlists"),
    "local": ("Local", "Your own media files"),
    "adult": ("Adult (opt-in)", "Requires [adult] enabled = true"),
}

_AVAILABLE: dict[str, type[Source]] = {
    "local": LocalSource,
    "stremio": StremioSource,
    "mediafusion": StremioSource,
    "knightcrawler": StremioSource,
    "torrentio-selfhost": StremioSource,
    "comet": CometSource,
    "aiostreams": AIOStreamsSource,
    "stremthru": StremThruStoreSource,
    "jackettio": JackettioSource,
    "deflix": DeflixSource,
    "stremify": StremifySource,
    "nuviostreams": NuvioStreamsSource,
    "horriblesubs": HorribleSubsSource,
    "aniworld": AniWorldSource,
    "otakustream": OtakuStreamSource,
    "yts": YTSSource,
    "rarbg": RARBGSource,
    "1337x": Thirteen37xSource,
    "piratebay": PirateBaySource,
    "tvmaze": TVMazeSource,
    "jikan": JikanSource,
    "kitsu": KitsuSource,
    "iptv": IPTVSource,
    "anilist": AnilistSource,
    "nyaa": NyaaSource,
    "subsplease": SubsPleaseSource,
    "tmdb": TMDBSource,
    "trakt": TraktSource,
    "stremio-adult": StremioAdultSource,
    "hanime": HanimeSource,
    "nhentai": NHentaiSource,
    "rule34": Rule34Source,
    "eztv-rss": EZTVRSSSource,
    "torrentgalaxy": TorrentGalaxySource,
    "magnetdl": MagnetDLSource,
    "vumoo": VumooSource,
    "solarmovie": SolarMovieSource,
    "stremio-community": StremioCommunitySource,
    "superstream": StremioSuperStreamSource,
    "torrentio-cloud": StremioTorrentioCloudSource,
    "limetorrents": LimeTorrentsSource,
    "torrentdownloads": TorrentDownloadsSource,
    "glodls": GloDLSSource,
    "iptv-org": IPTVOrgSource,
    "anidex": AniDexSource,
    "animetosho": AnimeToshoSource,
    "tokyotoshokan": TokyoToshokanSource,
    "thepiratebay": ThePirateBaySource,
    "rarbg-mirror": RARBGMirrorSource,
    "nyaa-torrents": NyaaTorrentsSource,
    "ehentai": EHentaiSource,
    "hitomila": HitomiLaSource,
    "hentaihaven": HentaiHavenSource,
}


def _stremio_kwargs(config: Config, source_id: str) -> dict:
    """Shared constructor args for every Stremio-protocol addon so
    per-source `[sources.<id>]` overrides and the global proxy apply."""
    source_cfg = config.sources_config.get(source_id, {})
    cinemeta_url = source_cfg.get("cinemeta_url") or config.stremio.cinemeta_url
    stream_url = source_cfg.get("stream_url")
    timeout = source_cfg.get("timeout_seconds", config.stremio.timeout_seconds)
    if not stream_url:
        # Defaults for ids sharing the base StremioSource class (no
        # subclass setdefault to fall back to). Subclasses (comet,
        # aiostreams, ...) define their own stream_url defaults via
        # kwargs.setdefault, so pass None and let those apply instead
        # of forcing everything onto the Torrentio URL.
        stream_url = {
            "mediafusion": "https://mediafusion.elfhosted.com",
            "knightcrawler": "https://knightcrawler.elfhosted.com",
            "torrentio-selfhost": "http://localhost:7000",
        }.get(source_id)
    kwargs = {
        "cinemeta_url": cinemeta_url,
        "timeout": timeout,
        "proxy_url": config.network.proxy_url,
        "source_id": source_id,
    }
    # Only pass stream_url when explicitly configured or for base-class
    # ids without a subclass default. Omitting the key lets subclass
    # kwargs.setdefault defaults (comet, aiostreams, ...) apply instead
    # of forcing everything onto the Torrentio URL.
    if stream_url:
        kwargs["stream_url"] = stream_url
    return kwargs


def load_sources(config: Config) -> list[Source]:
    import inspect
    import warnings

    sources = []
    for source_id in config.enabled_sources:
        cls = _AVAILABLE.get(source_id)
        if cls is None:
            warnings.warn(f"Unknown source id {source_id!r} in [sources] enabled — skipping")
            continue
        if issubclass(cls, StremioSource):
            # Every Stremio-protocol addon (stremio, mediafusion,
            # knightcrawler, torrentio-selfhost, comet, aiostreams,
            # stremthru, jackettio, deflix, stremify, ...)
            # shares this branch so per-source [sources.<id>] config
            # and the global proxy are honoured instead of silently
            # falling back to hardcoded defaults.
            sources.append(cls(**_stremio_kwargs(config, source_id)))
        elif issubclass(cls, (TVMazeSource, JikanSource, KitsuSource)):
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    api_url=source_cfg.get("api_url"),
                    stream_url=source_cfg.get("stream_url"),
                    cinemeta_url=source_cfg.get("cinemeta_url"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                    source_id=source_id,
                )
            )
        elif issubclass(cls, (YTSSource, RARBGSource, RARBGMirrorSource)):
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    api_url=source_cfg.get("api_url"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                )
            )
        elif issubclass(
            cls,
            (
                Thirteen37xSource,
                PirateBaySource,
                EZTVRSSSource,
                TorrentGalaxySource,
                MagnetDLSource,
                VumooSource,
                SolarMovieSource,
                LimeTorrentsSource,
                TorrentDownloadsSource,
                GloDLSSource,
            ),
        ):
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                )
            )
        elif cls is TMDBSource:
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    api_key=source_cfg.get("api_key"),
                    stream_url=source_cfg.get("stream_url"),
                    cinemeta_url=source_cfg.get("cinemeta_url"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                    source_id=source_id,
                )
            )
        elif cls is TraktSource:
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    client_id=source_cfg.get("client_id"),
                    client_secret=source_cfg.get("client_secret"),
                    stream_url=source_cfg.get("stream_url"),
                    cinemeta_url=source_cfg.get("cinemeta_url"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
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
            sources.append(
                cls(
                    m3u_url=m3u_url,
                    m3u_path=m3u_path,
                    timeout=timeout,
                    proxy_url=config.network.proxy_url,
                )
            )
        elif cls is IPTVOrgSource:
            # Free world playlist built in; overridable per usual.
            org_cfg = config.sources_config.get("iptv-org", {})
            timeout = org_cfg.get("timeout_seconds", config.iptv.timeout_seconds)
            sources.append(
                cls(
                    m3u_url=org_cfg.get("m3u_url"),
                    m3u_path=org_cfg.get("m3u_path"),
                    timeout=timeout,
                )
            )
        elif cls is ThePirateBaySource:
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    base_url=source_cfg.get("base_url"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                )
            )
        elif cls is NyaaTorrentsSource:
            source_cfg = config.sources_config.get(source_id, {})
            sources.append(
                cls(
                    mirror=source_cfg.get("mirror"),
                    timeout=source_cfg.get("timeout_seconds", config.stremio.timeout_seconds),
                    proxy_url=config.network.proxy_url,
                )
            )
        elif cls is AnilistSource:
            anilist_cfg = config.sources_config.get("anilist", {})
            include_adult = anilist_cfg.get("include_adult", False)
            try:
                params = inspect.signature(cls.__init__).parameters
            except (TypeError, ValueError):
                params = {}
            kwargs: dict = {"include_adult": include_adult}
            if "proxy_url" in params:
                kwargs["proxy_url"] = config.network.proxy_url
            if "timeout" in params:
                kwargs["timeout"] = anilist_cfg.get(
                    "timeout_seconds", config.stremio.timeout_seconds
                )
            sources.append(cls(**kwargs))
        elif cls in (
            StremioAdultSource,
            HanimeSource,
            NHentaiSource,
            Rule34Source,
            EHentaiSource,
            HitomiLaSource,
            HentaiHavenSource,
        ):
            # Adult sources need the full config for age gating
            sources.append(cls(config=config))
        else:
            # Generic fallback: honour global proxy/timeout when the
            # source supports them instead of silently ignoring config.
            try:
                params = inspect.signature(cls.__init__).parameters
            except (TypeError, ValueError):
                params = {}
            kwargs = {}
            if "proxy_url" in params:
                kwargs["proxy_url"] = config.network.proxy_url
            if "timeout" in params:
                kwargs["timeout"] = config.stremio.timeout_seconds
            try:
                sources.append(cls(**kwargs))
            except TypeError:
                sources.append(cls())
    return sources


def available_source_ids() -> list[str]:
    return list(_AVAILABLE.keys())


def sources_by_category() -> dict[str, list[tuple[str, type[Source]]]]:
    """Registered `(source_id, class)` pairs grouped by category, in
    display order; unknown categories trail at the end."""
    grouped: dict[str, list[tuple[str, type[Source]]]] = {cid: [] for cid in CATEGORIES}
    for source_id, cls in _AVAILABLE.items():
        category = getattr(cls, "category", "streams")
        grouped.setdefault(category, []).append((source_id, cls))
    return {cid: entries for cid, entries in grouped.items() if entries}
