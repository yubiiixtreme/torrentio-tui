"""Image caching and display for poster art."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App
from textual.widgets import Static

from torrentio_tui.config import cache_dir

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"

# Image cache directory
IMAGE_CACHE_DIR = cache_dir() / "posters"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(url: str) -> str:
    """Generate a cache filename from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16] + ".jpg"


def _get_cached_path(url: str) -> Path:
    """Get the cached file path for a URL."""
    return IMAGE_CACHE_DIR / _cache_key(url)


def is_cached(url: str) -> bool:
    """Check if an image is cached."""
    return _get_cached_path(url).exists()


def get_cached_path(url: str) -> Path | None:
    """Get cached image path if exists."""
    path = _get_cached_path(url)
    return path if path.exists() else None


async def download_image(app: App, url: str, timeout: float = 10.0) -> Path | None:
    """Download an image and cache it. Returns cached path or None on failure."""
    cached = get_cached_path(url)
    if cached:
        return cached

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "image/*"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            # Basic validation - check it's an image
            if not data[:4] in (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF"):
                return None
            cached.write_bytes(data)
            return cached
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None


class PosterWidget(Static):
    """Widget for displaying poster images with fallback."""

    def __init__(self, url: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poster_url = url
        self._loading = False

    async def set_poster(self, url: str | None) -> None:
        """Set poster URL and load image."""
        self.poster_url = url
        if not url:
            self._show_placeholder()
            return

        # Check cache first
        cached = get_cached_path(url)
        if cached and cached.exists():
            self._display_image(cached)
            return

        # Download async
        self._show_loading()
        app = self.app
        if app:
            path = await download_image(app, url)
            if path:
                self._display_image(path)
            else:
                self._show_placeholder()

    def _display_image(self, path: Path) -> None:
        """Display cached image."""
        try:
            # Textual 0.80+ supports images via Static
            self.styles.background = f"url('{path}')"
            self.styles.background_size = "cover"
            self.styles.background_position = "center"
            self.update("")
        except Exception:
            self._show_placeholder()

    def _show_loading(self) -> None:
        self.update("📥 Loading poster...")

    def _show_placeholder(self) -> None:
        self.update("🎬")

    def clear_poster(self) -> None:
        """Clear the poster."""
        self.poster_url = None
        self.styles.background = ""
        self.update("🍿")


async def preload_posters(app: App, urls: list[str]) -> None:
    """Preload multiple posters in background."""
    for url in urls:
        if url and not is_cached(url):
            await download_image(app, url)


def clear_cache() -> None:
    """Clear the image cache."""
    if IMAGE_CACHE_DIR.exists():
        shutil.rmtree(IMAGE_CACHE_DIR)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_size() -> int:
    """Get cache size in bytes."""
    total = 0
    for f in IMAGE_CACHE_DIR.glob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def cache_size_human() -> str:
    """Get human-readable cache size."""
    size = cache_size()
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
