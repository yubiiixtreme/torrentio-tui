"""Free content sources: Stremio-compatible addons for free movie/TV streaming.

These sources use the Stremio protocol with free addons that don't require
any API keys or subscriptions. They use the same Cinemeta catalogue for
metadata but different stream addons for actual playback links.

All of these are free, no API keys required, no geo-blocking, no paywalls.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from torrentio_tui.sources.base import Source
from torrentio_tui.sources.stremio import StremioSource

if TYPE_CHECKING:
    from torrentio_tui.config import Config


class CometSource(StremioSource):
    """Comet addon - free, open source Stremio addon."""
    id = "comet"
    name = "Comet (Free Addon)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://comet.strem.io")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Comet")
        super().__init__(**kwargs)


class DebridMediaManagerSource(StremioSource):
    """Debrid Media Manager - free addon for debrid users."""
    id = "debridmediamanager"
    name = "Debrid Media Manager"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://debridmediamanager.com")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Debrid Media Manager")
        super().__init__(**kwargs)


class YTSSource(StremioSource):
    """YTS/YIFY movies - high quality movie torrents."""
    id = "yts"
    name = "YTS / YIFY Movies"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://yts.mx")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "YTS")
        super().__init__(**kwargs)


class EZTVSource(StremioSource):
    """EZTV - TV show torrents."""
    id = "eztv"
    name = "EZTV Shows"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://eztv.re")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "EZTV")
        super().__init__(**kwargs)


class RARBGSource(StremioSource):
    """RARBG - general torrent index."""
    id = "rarbg"
    name = "RARBG"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://rarbg.to")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "RARBG")
        super().__init__(**kwargs)


class One337xSource(StremioSource):
    """1337x - general torrent index."""
    id = "1337x"
    name = "1337x"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://1337x.to")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "1337x")
        super().__init__(**kwargs)


class HorribleSubsSource(StremioSource):
    """HorribleSubs - anime subtitles (legacy, backup)."""
    id = "horriblesubs"
    name = "HorribleSubs (Legacy)"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://horriblesubs.info")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "HorribleSubs")
        super().__init__(**kwargs)


class SubsceneSource(StremioSource):
    """Subscene - subtitles."""
    id = "subscene"
    name = "Subscene"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://subscene.com")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "Subscene")
        super().__init__(**kwargs)


class OpenSubtitlesSource(StremioSource):
    """OpenSubtitles.org - subtitles."""
    id = "opensubtitles"
    name = "OpenSubtitles"

    def __init__(self, **kwargs):
        kwargs.setdefault("stream_url", "https://opensubtitles.org")
        kwargs.setdefault("cinemeta_url", "https://v3-cinemeta.strem.io")
        kwargs.setdefault("display_name", "OpenSubtitles")
        super().__init__(**kwargs)