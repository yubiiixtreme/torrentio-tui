from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.theme import Theme

from torrentio_tui.config import Config
from torrentio_tui.sources.base import Source
from torrentio_tui.themes import load_custom_themes
from torrentio_tui.ui.screens.main import MainScreen

TORRENTIO_THEME = Theme(
    name="torrentio",
    primary="#F5C518",  # Warm gold/yellow
    secondary="#A855F7",  # Purple
    accent="#E11D48",  # Rose red
    warning="#F5C518",
    error="#EF4444",
    success="#22C55E",  # Emerald green
    foreground="#F4F4F5",  # Zinc-100
    background="#0F172A",  # Slate-950
    surface="#1E293B",  # Slate-800
    panel="#1E293B",  # Slate-800
    boost="#334155",  # Slate-700
    dark=True,
)

OLED_BLACK_THEME = Theme(
    name="oled-black",
    primary="#FFFFFF",
    secondary="#00FFAA",
    accent="#00E5FF",
    warning="#FFD500",
    error="#FF3B30",
    success="#00E676",
    foreground="#FFFFFF",
    background="#000000",  # true black -- no backlight bleed on OLED panels
    surface="#050505",
    panel="#0A0A0A",
    boost="#1A1A1A",
    dark=True,
)

#: Built-in themes registered up front, before any user-supplied ones.
_BUILTIN_THEMES = (TORRENTIO_THEME, OLED_BLACK_THEME)


class TorrentioTuiApp(App):
    CSS_PATH = Path(__file__).parent / "app.tcss"
    TITLE = "🎬 Torrentio TUI"
    SUB_TITLE = "search · stream · watch"

    def __init__(self, sources: list[Source], config: Config) -> None:
        super().__init__()
        self.sources = sources
        self.config = config

    def on_mount(self) -> None:
        self.sync_custom_themes()
        wanted = self.config.ui.theme
        self.theme = wanted if wanted in self.available_themes else "torrentio"
        self.push_screen(MainScreen(self.sources, self.config))

    def sync_custom_themes(self) -> None:
        """(Re-)register the built-ins plus every theme file under
        ~/.config/torrentio-tui/themes/. Safe to call repeatedly -- Textual
        overwrites a theme registered under the same name, so this is how
        edited/newly-added theme files show up without restarting."""
        for theme in _BUILTIN_THEMES:
            self.register_theme(theme)
        for theme in load_custom_themes():
            self.register_theme(theme)
