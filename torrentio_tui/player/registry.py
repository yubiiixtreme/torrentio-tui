from __future__ import annotations

from torrentio_tui.player.base import Player
from torrentio_tui.player.mpv import MpvPlayer
from torrentio_tui.player.termux import TermuxPlayer
from torrentio_tui.player.vlc import VlcPlayer
from torrentio_tui.player.vlc_android import VlcAndroidPlayer

_BACKENDS: dict[str, type[Player]] = {
    "mpv": MpvPlayer,
    "vlc": VlcPlayer,
    "termux": TermuxPlayer,
    "vlc-android": VlcAndroidPlayer,
}


def get_player(backend_id: str, hwdec: str = "") -> Player:
    cls = _BACKENDS.get(backend_id)
    if cls is None:
        raise ValueError(f"Unknown player backend: {backend_id!r}")
    if cls is MpvPlayer:
        return cls(hwdec=hwdec)
    return cls()


def available_player_ids() -> list[str]:
    return list(_BACKENDS.keys())
