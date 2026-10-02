"""Poster art: download, cache, and render.

Real image rendering needs the optional `textual-image` dependency
(`pip install torrentio-tui[images]`) — it auto-detects the terminal's
graphics protocol (Kitty, iTerm2, Sixel) and falls back to a Unicode
half-block approximation everywhere else, so it renders *something*
real in virtually any color terminal. It pulls in Pillow, which isn't
guaranteed to have a prebuilt wheel on every platform (Termux/ARM being
the main case), so it's optional rather than a hard dependency — without
it, PosterWidget falls back to a plain colored icon card instead of
failing to install at all.
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from textual.containers import Container
from textual.widgets import Static

from torrentio_tui.config import cache_dir
from torrentio_tui.retry import call_with_backoff

try:
    from textual_image.widget import Image as _ImageWidget

    IMAGES_AVAILABLE = True
except ImportError:
    _ImageWidget = None
    IMAGES_AVAILABLE = False

_USER_AGENT = "torrentio-tui/0.6 (+https://github.com/yubiiixtreme/torrentio-tui)"

IMAGE_CACHE_DIR = cache_dir() / "posters"

_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF")


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16] + ".img"


def _cached_path(url: str) -> Path:
    return IMAGE_CACHE_DIR / _cache_key(url)


class _RetryableFetchError(Exception):
    pass


def _fetch(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "image/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        # Timeouts/drops and 5xx/429 are worth retrying; any other 4xx means
        # the poster genuinely isn't there, so let it propagate immediately.
        if exc.code == 429 or exc.code >= 500:
            raise _RetryableFetchError(str(exc)) from exc
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _RetryableFetchError(str(exc)) from exc


def download_image(url: str, timeout: float = 10.0) -> Path | None:
    """Download (or reuse a cached copy of) an image. Returns the local
    path, or None if the download failed or wasn't actually an image.
    Retries transient failures (timeouts, dropped connections, 5xx/429)
    with exponential backoff; a genuine 4xx is not retried. Blocking —
    call this from a thread worker, not the UI thread.
    """
    cached = _cached_path(url)
    if cached.exists():
        return cached

    try:
        data = call_with_backoff(lambda: _fetch(url, timeout), retryable=_RetryableFetchError)
    except (urllib.error.HTTPError, _RetryableFetchError):
        return None

    # Cheap sniff; not exhaustive, just enough to reject HTML error pages.
    if not any(data.startswith(magic) for magic in _IMAGE_MAGIC):
        return None

    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    except OSError:
        return None
    return cached


class PosterWidget(Container):
    """Poster display: a real rendered image when textual-image is
    installed and the download succeeds, otherwise a colored icon card
    showing the content kind — always something, never a blank box.
    """

    DEFAULT_CSS = """
    PosterWidget {
        align: center middle;
    }
    PosterWidget > Static {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-style: bold;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fallback = Static("🍿", id="poster-fallback")

    def compose(self):
        yield self._fallback

    def _remove(self, child) -> None:
        # On the Kitty Graphics Protocol (kitty, WezTerm, Ghostty, ...), a
        # placed image is only deleted from the terminal by textual-image's
        # own `.image = None` setter -- a plain widget `.remove()` skips
        # that and leaves the old poster's pixels ghosted on screen behind
        # whatever gets drawn next. Clearing `.image` first (a no-op for
        # Sixel/Unicode, which have nothing terminal-side to release) is
        # what actually frees it before the widget itself is removed.
        if _ImageWidget is not None and isinstance(child, _ImageWidget):
            child.image = None
        child.remove()

    def show_fallback(self, icon: str, color: str = "gray") -> None:
        """Show the icon-card fallback (no poster URL, download failed, or
        textual-image isn't installed)."""
        self.styles.border = ("round", color)
        for child in list(self.children):
            if child is not self._fallback:
                self._remove(child)
        if not self._fallback.is_mounted:
            self.mount(self._fallback)
        self._fallback.update(icon)
        self._fallback.display = True

    def show_image(self, path: Path) -> None:
        """Render a real downloaded image (only called when textual-image
        is available and the download succeeded)."""
        if _ImageWidget is None:
            return
        for child in list(self.children):
            self._remove(child)
        self._fallback.display = False
        self.mount(_ImageWidget(str(path)))


def clear_cache() -> None:
    if IMAGE_CACHE_DIR.exists():
        shutil.rmtree(IMAGE_CACHE_DIR)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_size_human() -> str:
    total = sum(f.stat().st_size for f in IMAGE_CACHE_DIR.glob("*") if f.is_file())
    size = float(total)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
