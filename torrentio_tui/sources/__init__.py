"""Source implementations package."""

from torrentio_tui.sources.adult import (
    HanimeSource,
    NHentaiSource,
    Rule34Source,
    StremioAdultSource,
)
from torrentio_tui.sources.anime import AnilistSource, NyaaSource, SubsPleaseSource
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.sources.catalogues import JikanSource, KitsuSource, TVMazeSource
from torrentio_tui.sources.free import (
    AIOStreamsSource,
    CometSource,
    DeflixSource,
    JackettioSource,
    StremifySource,
    StremThruStoreSource,
)
from torrentio_tui.sources.iptv import IPTVSource
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.sources.stremio import StremioSource
from torrentio_tui.sources.subtitles import (
    OpenSubtitlesProvider,
    SubDBProvider,
    SubtitleFile,
    SubtitleProvider,
    attach_subtitles,
    available_provider_ids,
    load_subtitle_providers,
)
from torrentio_tui.sources.torrentapi import YTSSource

__all__ = [
    "Source",
    "SourceError",
    "LocalSource",
    "StremioSource",
    "CometSource",
    "AIOStreamsSource",
    "StremThruStoreSource",
    "JackettioSource",
    "DeflixSource",
    "StremifySource",
    "YTSSource",
    "TVMazeSource",
    "JikanSource",
    "KitsuSource",
    "IPTVSource",
    "AnilistSource",
    "NyaaSource",
    "SubsPleaseSource",
    "StremioAdultSource",
    "HanimeSource",
    "NHentaiSource",
    "Rule34Source",
    "SubtitleProvider",
    "SubtitleFile",
    "SubDBProvider",
    "OpenSubtitlesProvider",
    "attach_subtitles",
    "available_provider_ids",
    "load_subtitle_providers",
]
