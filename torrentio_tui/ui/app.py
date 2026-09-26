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

# Ultra-minimal CSS for Textual 8.2.8 — only basic properties that work
TORRENTIO_CSS = r"""
/* Torrentio TUI — Minimal Theme (Textual 8.2.8) */

Screen { background: $background; }
* { color: $foreground; }

Header {
    background: $panel;
    color: $primary;
    text-style: bold;
    height: 3;
    border-bottom: thick $primary;
}
Header > .header-title {
    color: $primary;
    text-style: bold;
    padding: 0 2;
}
Header > .header-clock { color: $warning; text-style: bold; }

Footer { background: $panel; border-top: thick $secondary; }
.footer-key-foreground { color: $primary; text-style: bold; }
.footer-key-background { background: $surface; color: $secondary; text-style: bold; }

Tabs { background: $panel; border-bottom: thick $foreground 20%; }
Tab { padding: 0 4; margin: 0 1; color: $foreground 40%; text-style: bold; border: round transparent; }
Tab:hover { color: $primary; background: $surface; border: round $primary; }
Tab.-active { color: $primary; background: $panel; border: round $primary; text-style: bold underline; }
Underline { color: $primary; background: $primary; height: 2; }

#search-input {
    border: thick $panel; background: $surface; margin: 1 2; padding: 1 2; color: $foreground;
}
#search-input:focus { border: thick $primary; background: $panel; }
#search-input::placeholder { color: $foreground 20%; text-style: italic; }

#search-loading { height: 3; content-align: center middle; color: $primary; text-style: bold; }

#search-body { layout: horizontal; height: 1fr; margin: 1 2 2 2; }
.results-panel {
    width: 2fr; background: $panel; border: round $foreground 20%;
    scrollbar-color: $primary; scrollbar-background: $surface; scrollbar-size: 1 1;
}
.results-panel:focus, .results-panel:hover { border: round $primary; }
#detail-panel {
    width: 1fr; min-width: 38; margin: 1 2 2 1; padding: 1 2;
    background: $panel; border: round $foreground 20%;
}
#detail-panel:focus, #detail-panel:hover { border: round $secondary; }

ListView > ResultItem, ListView > HistoryItem {
    height: auto; min-height: 3; background: transparent;
    border-left: thick transparent; margin: 0 1; padding: 0 1;
}
ResultItem.kind-movie { border-left-color: $primary; }
ResultItem.kind-series { border-left-color: $success; }
ResultItem.kind-anime { border-left-color: $secondary; }
ResultItem.kind-live { border-left-color: $error; }
HistoryItem { border-left-color: $warning; }
ListView > ListItem.--highlight { background: $panel; border-left: thick $primary; }
ListView:focus > ListItem.--highlight { background: $surface; border-left: thick $warning; }
ResultItem Static, HistoryItem Static { height: auto; padding: 0 1; }

.kind-badge { width: 6; height: 1; content-align: center middle; text-style: bold; margin-right: 1; border: round $panel; }
.kind-badge.movie { background: $primary; color: $background; }
.kind-badge.series { background: $success; color: $background; }
.kind-badge.anime { background: $secondary; color: $foreground; }
.kind-badge.live { background: $error; color: $foreground; }

#detail-poster {
    height: 18; width: 100%; content-align: center middle;
    background: $surface; border: round $foreground 20%; margin-bottom: 1; overflow: hidden;
}
#detail-poster > Static { width: 100%; height: 100%; background: $panel; }
.poster-placeholder { color: $foreground 40%; text-style: bold; }

#detail-title { text-style: bold; height: auto; margin-bottom: 1; color: $primary; }
#detail-meta { color: $foreground 60%; height: auto; margin-bottom: 1; line-height: 1.5; }
#detail-meta > Span { margin-right: 2; }
.meta-year { color: $warning; }
.meta-kind { color: $primary; }
.meta-source { color: $secondary; }
#detail-genres { height: auto; margin-bottom: 1; color: $foreground 40%; }
.genre-tag { background: $surface; color: $warning; padding: 0 1; margin-right: 1; border: round $foreground 20%; text-style: bold; }
#detail-overview {
    height: 1fr; color: $foreground 60%; line-height: 1.4;
    overflow-y: auto; scrollbar-color: $secondary; scrollbar-background: transparent; scrollbar-size: 1 1;
}

#status-line {
    dock: bottom; height: 1; padding: 0 2;
    background: $panel; color: $foreground 40%; border-top: thick $foreground 20%; text-style: italic;
}

ModalScreen { background: $background 85%; }
#episode-list-container, #quality-list-container {
    width: 70%; height: 70%; margin: 4 8; border: thick $primary; background: $panel;
}
#episode-title, #quality-title {
    height: 1; padding: 0 2; background: $primary; color: $background; text-style: bold; border-bottom: thick $primary;
}
#episode-list-container ListView, #quality-list-container ListView {
    background: $surface; scrollbar-color: $primary; scrollbar-background: transparent; scrollbar-size: 1 1; height: 1fr;
}
#episode-list-container ListItem, #quality-list-container ListItem {
    height: auto; min-height: 2; padding: 0 2; margin: 0 1; border-left: thick transparent;
}
#episode-list-container ListItem.--highlight, #quality-list-container ListItem.--highlight {
    background: $panel; border-left: thick $warning;
}

.quality-tag {
    background: $panel; color: $success; padding: 0 1; margin-right: 1;
    border: round $foreground 20%; text-style: bold;
}
.quality-tag.direct { color: $primary; }
.quality-tag.magnet { color: $warning; }
.quality-tag.debrid { color: $warning; }

ScrollBar { background: $surface; }
ScrollBar > Slider { background: $primary; border: round $primary; min-height: 20; }
ScrollBar > Slider:hover { background: $secondary; border: round $secondary; }
ScrollBar > Button { display: none; }

Toast { background: $panel; border: round $primary; color: $foreground; padding: 1 2; }

Input { border: thick $panel; background: $surface; }
Input:focus { border: thick $primary; }

Button { background: $panel; color: $foreground; border: round $foreground 20%; padding: 0 3; margin: 0 1; }
Button:hover { background: $primary; color: $background; border: round $primary; text-style: bold; }
Button:focus { border: thick $warning; }

ProgressBar { background: $surface; border: round $foreground 20%; }
ProgressBar > Bar { background: $primary; border: round $primary; }

DataTable { background: $surface; }
DataTable > .datatable--header { background: $panel; color: $primary; text-style: bold; }
DataTable > .datatable--cursor { background: $panel; }

@media (max-width: 100) {
    #search-body { layout: vertical; }
    .results-panel { width: 100%; height: 1fr; }
    #detail-panel { width: 100%; min-width: 0; height: 40%; margin: 0 2 2 2; }
}
"""

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