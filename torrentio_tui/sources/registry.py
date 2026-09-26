"""Wires source ids (from config) to `Source` instances.

Add your own source here once it's implemented:

    from torrentio_tui.sources.mysource import MySource
    _AVAILABLE["mysource"] = MySource
"""

from __future__ import annotations

from torrentio_tui.sources.base import Source
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.sources.stremio import StremioSource

_AVAILABLE: dict[str, type[Source]] = {
    "local": LocalSource,
    "stremio": StremioSource,
}


def load_sources(
    enabled_ids: list[str],
    stremio_cinemeta_url: str | None = None,
    stremio_stream_url: str | None = None,
    stremio_timeout: float = 15.0,
    proxy_url: str | None = None,
) -> list[Source]:
    sources = []
    for source_id in enabled_ids:
        cls = _AVAILABLE.get(source_id)
        if cls is None:
            continue
        if cls is StremioSource:
            sources.append(
                cls(
                    cinemeta_url=stremio_cinemeta_url,
                    stream_url=stremio_stream_url,
                    timeout=stremio_timeout,
                    proxy_url=proxy_url,
                )
            )
        else:
            sources.append(cls())
    return sources


def available_source_ids() -> list[str]:
    return list(_AVAILABLE.keys())
