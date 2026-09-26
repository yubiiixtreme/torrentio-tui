from __future__ import annotations

from stream_tui.player.base import Player
from stream_tui.player.mpv import MpvPlayer
from stream_tui.player.vlc import VlcPlayer

_BACKENDS: dict[str, type[Player]] = {
    "mpv": MpvPlayer,
    "vlc": VlcPlayer,
}


def get_player(backend_id: str) -> Player:
    cls = _BACKENDS.get(backend_id)
    if cls is None:
        raise ValueError(f"Unknown player backend: {backend_id!r}")
    return cls()
