from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.theme import Theme

from torrentio_tui.config import Config
from torrentio_tui.sources.base import Source
from torrentio_tui.themes import load_custom_themes
from torrentio_tui.ui.screens.main import MainScreen

# ============================================================================
# CYBERPUNK / SCI-FI THEMES
# ============================================================================

TORRENTIO_THEME = Theme(
    name="torrentio",
    # Cyberpunk palette
    primary="#00ffff",  # Neon cyan
    secondary="#ff00ff",  # Neon magenta
    accent="#ffbf00",  # Neon amber
    warning="#ffbf00",  # Amber
    error="#ff073a",  # Neon red
    success="#00ff41",  # Matrix green
    foreground="#e0ffff",  # Bright cyan
    background="#020617",  # Void 950
    surface="#0c1426",  # Void 900
    panel="#111e3a",  # Void 800
    boost="#1a2d50",  # Void 700
    dark=True,
)

OLED_BLACK_THEME = Theme(
    name="oled-black",
    primary="#00ffff",
    secondary="#ff00ff",
    accent="#ffbf00",
    warning="#ffbf00",
    error="#ff073a",
    success="#00ff41",
    foreground="#e0ffff",
    background="#000000",  # True black
    surface="#050505",
    panel="#0a0a0a",
    boost="#1a1a1a",
    dark=True,
)

# Matrix theme
MATRIX_THEME = Theme(
    name="matrix",
    primary="#00ff41",  # Matrix green
    secondary="#00cc33",  # Dim green
    accent="#ffff00",  # Yellow
    warning="#ffff00",
    error="#ff073a",
    success="#00ff41",
    foreground="#00ff41",
    background="#000000",
    surface="#001a00",
    panel="#001100",
    boost="#002200",
    dark=True,
)

# Void theme
VOID_THEME = Theme(
    name="void",
    primary="#00ffff",
    secondary="#ff00ff",
    accent="#ffbf00",
    warning="#ffbf00",
    error="#ff073a",
    success="#00ff41",
    foreground="#e0ffff",
    background="#000000",
    surface="#000000",
    panel="#000000",
    boost="#050505",
    dark=True,
)

# Synthwave theme
SYNTHWAVE_THEME = Theme(
    name="synthwave",
    primary="#ff00ff",
    secondary="#00ffff",
    accent="#ffbf00",
    warning="#ffbf00",
    error="#ff073a",
    success="#00ff41",
    foreground="#ffe0ff",
    background="#1a0033",
    surface="#2d004d",
    panel="#3d0066",
    boost="#4d0080",
    dark=True,
)

# Amber/Monochrome theme
AMBER_THEME = Theme(
    name="amber",
    primary="#ffbf00",
    secondary="#cc9900",
    accent="#ff8c00",
    warning="#ffbf00",
    error="#ff3300",
    success="#00cc33",
    foreground="#ffcc00",
    background="#000000",
    surface="#1a1100",
    panel="#261a00",
    boost="#332200",
    dark=True,
)

# Built-in themes registered up front
_BUILTIN_THEMES = (
    TORRENTIO_THEME,
    OLED_BLACK_THEME,
    MATRIX_THEME,
    VOID_THEME,
    SYNTHWAVE_THEME,
    AMBER_THEME,
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
        self.sync_custom_themes()
        wanted = self.config.ui.theme
        self.theme = wanted if wanted in self.available_themes else "torrentio"
        self.push_screen(MainScreen(self.sources, self.config))

    def watch_theme(self, theme: str) -> None:
        """Persist every theme change — `t` cycling, the Ctrl+P theme
        picker, anything else that sets `app.theme` — so the selection is
        the default next launch. Runs on startup too, where it just
        re-saves the already-stored value (harmless)."""
        from torrentio_tui.config import save_theme

        self.config.ui.theme = theme
        save_theme(theme)

    def sync_custom_themes(self) -> None:
        """(Re-)register the built-ins plus every theme file under
        ~/.config/torrentio-tui/themes/. Safe to call repeatedly -- Textual
        overwrites a theme registered under the same name, so this is how
        edited/newly-added theme files show up without restarting."""
        for theme in _BUILTIN_THEMES:
            self.register_theme(theme)
        for theme in load_custom_themes():
            self.register_theme(theme)
