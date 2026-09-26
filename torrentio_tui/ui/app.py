from __future__ import annotations

from pathlib import Path

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


class TorrentioTuiApp(App):
    CSS_PATH = Path(__file__).parent / "app.tcss"
    TITLE = "🎬 Torrentio TUI"
    SUB_TITLE = "search · stream · watch"

    def __init__(self, sources: list[Source], config: Config) -> None:
        super().__init__()
        self.sources = sources
        self.config = config

    def on_mount(self) -> None:
        self.register_theme(TORRENTIO_THEME)
        self.theme = "torrentio"
        self.push_screen(MainScreen(self.sources, self.config))
