"""Source implementations package."""

from torrentio_tui.sources.adult import (
    HanimeSource,
    NHentaiSource,
    Rule34Source,
    StremioAdultSource,
)
from torrentio_tui.sources.anime import AnilistSource, NyaaSource, SubsPleaseSource
from torrentio_tui.sources.base import Source, SourceError
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

__all__ = [
    "Source",
    "SourceError",
    "LocalSource",
    "StremioSource",
    "CometSource",
    "DebridMediaManagerSource",
    "YTSSource",
    "EZTVSource",
    "RARBGSource",
    "One337xSource",
    "HorribleSubsSource",
    "SubsceneSource",
    "OpenSubtitlesSource",
    "IPTVSource",
    "AnilistSource",
    "NyaaSource",
    "SubsPleaseSource",
    "StremioAdultSource",
    "HanimeSource",
    "NHentaiSource",
    "Rule34Source",
]
