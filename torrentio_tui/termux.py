"""Termux (Android) environment detection.

Termux has no framebuffer/GUI of its own, so mpv/vlc terminal video output
doesn't work there. `player/termux.py` hands playback off to whatever
video app is installed on the device instead, via `termux-open` (part of
the `termux-api` package + the companion Termux:API app from F-Droid/Play).
"""

from __future__ import annotations

import os


def is_termux() -> bool:
    if os.environ.get("TERMUX_VERSION"):
        return True
    return "com.termux" in os.environ.get("PREFIX", "")
