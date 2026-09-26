from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.theme import Theme

from torrentio_tui.config import Config
from torrentio_tui.sources.base import Source
from torrentio_tui.ui.screens.main import MainScreen

TORRENTIO_THEME = Theme(
    name="torrentio",
    primary="#F5C518",       # Warm gold/yellow
    secondary="#A855F7",     # Purple
    accent="#E11D48",        # Rose red
    warning="#F5C518",
    error="#EF4444",
    success="#22C55E",       # Emerald green
    foreground="#F4F4F5",    # Zinc-100
    background="#0F172A",    # Slate-950
    surface="#1E293B",       # Slate-800
    panel="#1E293B",         # Slate-800
    boost="#334155",         # Slate-700
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
