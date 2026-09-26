from __future__ import annotations

from textual.app import App
from textual.theme import Theme

from torrentio_tui.config import Config
from torrentio_tui.sources.base import Source
from torrentio_tui.ui.screens.main import MainScreen

TORRENTIO_THEME = Theme(
    name="torrentio",
    primary="#F5C518",
    secondary="#8B5CF6",
    accent="#E50914",
    warning="#F5C518",
    error="#E74C3C",
    success="#2ECC71",
    foreground="#E8E8E8",
    background="#090A0F",
    surface="#12141C",
    panel="#1A1D28",
    dark=True,
)

# No custom CSS — use Textual defaults + theme colors (works on all versions)
TORRENTIO_CSS = ""

# Sentinel class: truthy for 'or' check, but iterates to empty list
class _EmptyCssPath(list):
    def __bool__(self) -> bool:
        return True
    def __iter__(self):
        return iter([])


class TorrentioTuiApp(App):
    CSS_PATH = []
    CSS = TORRENTIO_CSS
    TITLE = "🎬 Torrentio TUI"
    SUB_TITLE = "search · stream · watch"

    def __init__(self, sources: list[Source], config: Config) -> None:
        super().__init__(css_path=_EmptyCssPath())
        self.sources = sources
        self.config = config

    def on_mount(self) -> None:
        self.register_theme(TORRENTIO_THEME)
        self.theme = "torrentio"
        self.push_screen(MainScreen(self.sources, self.config))