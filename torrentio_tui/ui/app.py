from __future__ import annotations

from pathlib import Path

from textual.app import App

from torrentio_tui.config import Config
from torrentio_tui.sources.base import Source
from torrentio_tui.ui.screens.main import MainScreen


class TorrentioTuiApp(App):
    CSS_PATH = Path(__file__).parent / "app.tcss"
    TITLE = "Torrentio TUI"

    def __init__(self, sources: list[Source], config: Config) -> None:
        super().__init__()
        self.sources = sources
        self.config = config

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.sources, self.config))
