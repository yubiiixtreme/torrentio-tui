"""Source implementations package."""

from torrentio_tui.sources.adult import HanimeSource, StremioAdultSource
from torrentio_tui.sources.anime import AnilistSource, NyaaSource, SubsPleaseSource
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.sources.iptv import IPTVSource
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.sources.stremio import StremioSource

__all__ = [
    "Source",
    "SourceError",
    "LocalSource",
    "StremioSource",
    "IPTVSource",
    "AnilistSource",
    "NyaaSource",
    "SubsPleaseSource",
    "StremioAdultSource",
    "HanimeSource",
]
