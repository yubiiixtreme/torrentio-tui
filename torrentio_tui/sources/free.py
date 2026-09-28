"""Stremio-protocol stream addons (free, no API keys).

Every class here speaks Stremio's `/stream/{type}/{videoId}.json`
protocol and reuses `StremioSource` for catalogue (Cinemeta) +
search, only swapping the stream backend. Addons that need personal
configuration (AIOStreams, StremThru, Deflix, ...) work with their
public/shared defaults where one exists, but paste your *configured*
URL from the addon's own `/configure` page into
`[sources.<id>] stream_url` for the full experience (debrid keys,
private trackers, higher rate limits).

Verified reachable 2026-09: AIOStreams, StremThru and Jackettio
public instances; Comet and MediaFusion as before.
Knightcrawler's public instance was retired by ElfHosted (project
ceased development in 2024) — the id stays registered for existing
configs but is no longer recommended.
"""

from __future__ import annotations

from torrentio_tui.sources.stremio import StremioSource


class CometSource(StremioSource):
    """Comet addon - free, open source Stremio addon."""

    id = "comet"
    name = "Comet (Free Addon)"

    def __init__(self, **kwargs):
        # Public instance moved from comet.strem.io (dead) to ElfHosted.
        kwargs.setdefault("stream_url", "https://comet.elfhosted.com")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Comet")
        super().__init__(**kwargs)


class AIOStreamsSource(StremioSource):
    """AIOStreams — super-addon merging 80+ community addons with unified
    filtering/sorting. Paste your configured URL for debrid + full addons."""

    id = "aiostreams"
    name = "AIOStreams (Super-Addon)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://aiostreams.elfhosted.com")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "AIOStreams")
        super().__init__(**kwargs)


class StremThruStoreSource(StremioSource):
    """StremThru Store — search your debrid-store catalog (RealDebrid,
    AllDebrid, TorBox, ...). Needs your store token: paste the configured
    URL from the StremThru dashboard."""

    id = "stremthru"
    name = "StremThru Store (Debrid Catalog)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://stremthru.elfhosted.com/stremio/store")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "StremThru")
        super().__init__(**kwargs)


class JackettioSource(StremioSource):
    """Jackettio — Jackett-backed streams (public + private trackers)
    resolved through debrid. Public ElfHosted instance works out of the
    box; self-host for private trackers."""

    id = "jackettio"
    name = "Jackettio (Jackett + Debrid)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://jackettio.elfhosted.com")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Jackettio")
        super().__init__(**kwargs)


class DeflixSource(StremioSource):
    """Deflix — self-hosted addon turning YTS/TPB/1337x/RARBG torrents
    into cached debrid HTTP streams. Run `deflix-stremio` locally, then
    point `stream_url` at it (default http://localhost:8080)."""

    id = "deflix"
    name = "Deflix (Self-Hosted Debrid)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "http://localhost:8080")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Deflix")
        super().__init__(**kwargs)


class StremifySource(StremioSource):
    """Stremify — self-hosted addon streaming via movie-web providers
    (incl. non-English sources). Run it locally, then point `stream_url`
    at it (default http://localhost:3000)."""

    id = "stremify"
    name = "Stremify (Self-Hosted Providers)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "http://localhost:3000")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Stremify")
        super().__init__(**kwargs)


class NuvioStreamsSource(StremioSource):
    """NuvioStreams — free Stremio addon with multi-source streams."""

    id = "nuviostreams"
    name = "NuvioStreams"
    category = "streams"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://nuviostreams.hayd.uk")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "NuvioStreams")
        super().__init__(**kwargs)


class HorribleSubsSource(StremioSource):
    """HorribleSubs — legacy anime releases (now mostly historical,
    kept for completeness)."""

    id = "horriblesubs"
    name = "HorribleSubs (Legacy)"
    category = "anime"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://horriblesubs.info")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "HorribleSubs")
        super().__init__(**kwargs)


class AniWorldSource(StremioSource):
    """AniWorld — German anime streaming addon."""

    id = "aniworld"
    name = "AniWorld (German Anime)"
    category = "anime"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://aniworld.to/stremio")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "AniWorld")
        super().__init__(**kwargs)


class OtakuStreamSource(StremioSource):
    """OtakuStream — anime-focused Stremio addon."""

    id = "otakustream"
    name = "OtakuStream (Anime)"
    category = "anime"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://otakustream.strem.io")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "OtakuStream")
        super().__init__(**kwargs)
