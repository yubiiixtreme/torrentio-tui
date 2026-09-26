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

# Embedded CSS — works in all installation modes (pipx, pip, dev, etc.)
TORRENTIO_CSS = r"""
/* ═══════════════════════════════════════════════════════════════════════════
   Torrentio TUI — Fancy Theme
   Modern, animated, colorful Textual CSS with poster art support
   ════════════════════════════════════════════════════════════════════════════ */

/* ─── Color palette (Dracula-inspired with cyberpunk accents) ─── */
:root {
    /* Base surfaces */
    --bg-deep:          #0d0d1a;
    --bg-surface:       #1a1a2e;
    --bg-panel:         #24243e;
    --bg-boost:         #2d2d4e;
    --bg-hover:         #32325a;

    /* Accents */
    --accent-cyan:      #00ffff;
    --accent-magenta:   #ff00ff;
    --accent-gold:      #ffd700;
    --accent-orange:    #ff6b00;
    --accent-green:     #00ff88;
    --accent-red:       #ff3366;
    --accent-blue:      #0088ff;
    --accent-purple:    #aa00ff;

    /* Text */
    --fg-primary:       #f8f8f2;
    --fg-secondary:     #b8b8d0;
    --fg-muted:         #626282;
    --fg-dim:           #444466;

    /* Kind colors */
    --kind-movie:       #00ffff;
    --kind-series:      #00ff88;
    --kind-anime:       #ff00ff;
    --kind-live:        #ff3366;

    /* Gradients */
    --grad-primary:     linear-gradient(135deg, #00ffff 0%, #ff00ff 100%);
    --grad-secondary:   linear-gradient(135deg, #ffd700 0%, #ff6b00 100%);
    --grad-success:     linear-gradient(135deg, #00ff88 0%, #00ccaa 100%);
    --grad-danger:      linear-gradient(135deg, #ff3366 0%, #ff0099 100%);
    --grad-panel:       linear-gradient(180deg, #24243e 0%, #1a1a2e 100%);
    --grad-glass:       linear-gradient(135deg, rgba(36,36,62,0.9) 0%, rgba(26,26,46,0.7) 100%);
}

/* ─── Global ─── */
Screen {
    background: var(--bg-deep);
    layers: base overlays popovers;
}

* {
    color: var(--fg-primary);
}

/* ─── Animations ─── */
@keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slide-up {
    from { opacity: 0; offset: 0 2; }
    to { opacity: 1; offset: 0 0; }
}

@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 0 var(--accent-cyan); }
    50% { box-shadow: 0 0 8 var(--accent-cyan); }
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes spin {
    to { rotate: 360deg; }
}

.animate-fade-in {
    animation: fade-in 300ms ease-out;
}

.animate-slide-up {
    animation: slide-up 400ms ease-out;
}

.animate-pulse {
    animation: pulse-glow 2s ease-in-out infinite;
}

.animate-shimmer {
    background: var(--grad-primary);
    background-size: 200% 100%;
    animation: shimmer 2s linear infinite;
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

/* ─── Header ─── */
Header {
    background: var(--grad-panel);
    color: var(--fg-primary);
    text-style: bold;
    height: 3;
    border-bottom: thick var(--accent-cyan);
    animation: fade-in 400ms ease-out;
}

Header > .header-title {
    background: var(--grad-primary);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    text-style: bold;
    padding: 0 2;
}

Header > .header-clock {
    color: var(--accent-gold);
    text-style: bold;
}

/* ─── Footer ─── */
Footer {
    background: var(--grad-panel);
    border-top: thick var(--accent-magenta);
}

.footer-key-foreground {
    color: var(--accent-cyan);
    text-style: bold;
}

.footer-key-background {
    background: var(--bg-surface);
    color: var(--accent-magenta);
    text-style: bold;
}

/* ─── Tabs ─── */
Tabs {
    background: var(--bg-panel);
    border-bottom: thick var(--fg-dim);
}

Tab {
    padding: 0 4;
    margin: 0 1;
    color: var(--fg-muted);
    text-style: bold;
    border: round transparent;
    transition: color 150ms, background 150ms, border 150ms;
}

Tab:hover {
    color: var(--accent-cyan);
    background: var(--bg-hover);
    border: round var(--accent-cyan);
}

Tab.-active {
    color: var(--accent-cyan);
    background: var(--bg-boost);
    border: round var(--accent-cyan);
    text-style: bold underline;
}

Underline {
    color: var(--accent-cyan);
    background: var(--grad-primary);
    height: 2;
}

/* ─── Input ─── */
#search-input {
    border: thick var(--bg-panel);
    background: var(--bg-surface);
    margin: 1 2;
    padding: 1 2;
    color: var(--fg-primary);
    transition: border 200ms, background 200ms, box-shadow 200ms;
}

#search-input:focus {
    border: thick var(--accent-cyan);
    background: var(--bg-panel);
    box-shadow: 0 0 4 var(--accent-cyan);
}

#search-input::placeholder {
    color: var(--fg-dim);
    text-style: italic;
}

/* ─── Loading spinner ─── */
#search-loading {
    height: 3;
    content-align: center middle;
    color: var(--accent-cyan);
    text-style: bold;
}

/* ─── Results panels ─── */
#search-body {
    layout: horizontal;
    height: 1fr;
    margin: 1 2 2 2;
}

.results-panel {
    width: 2fr;
    background: var(--grad-glass);
    border: round var(--fg-dim);
    scrollbar-color: var(--accent-cyan);
    scrollbar-background: var(--bg-surface);
    scrollbar-size: 1 1;
    transition: border 200ms, box-shadow 200ms;
}

.results-panel:focus,
.results-panel:hover {
    border: round var(--accent-cyan);
    box-shadow: 0 0 8 var(--accent-cyan);
}

#detail-panel {
    width: 1fr;
    min-width: 38;
    margin: 1 2 2 1;
    padding: 1 2;
    background: var(--grad-glass);
    border: round var(--fg-dim);
    transition: border 200ms, box-shadow 200ms;
}

#detail-panel:focus,
#detail-panel:hover {
    border: round var(--accent-magenta);
    box-shadow: 0 0 8 var(--accent-magenta);
}

/* ─── List items ─── */
ListView > ResultItem,
ListView > HistoryItem {
    height: auto;
    min-height: 3;
    background: transparent;
    border-left: thick transparent;
    margin: 0 1;
    padding: 0 1;
    transition: background 150ms, border 150ms, transform 150ms;
}

ResultItem.kind-movie { border-left-color: var(--kind-movie); }
ResultItem.kind-series { border-left-color: var(--kind-series); }
ResultItem.kind-anime { border-left-color: var(--kind-anime); }
ResultItem.kind-live { border-left-color: var(--kind-live); }

HistoryItem { border-left-color: var(--accent-gold); }

ListView > ListItem.--highlight {
    background: var(--bg-boost);
    border-left: thick var(--accent-cyan);
    transform: scale(1.01);
}

ListView:focus > ListItem.--highlight {
    background: var(--bg-hover);
    border-left: thick var(--accent-gold);
}

ResultItem Static, HistoryItem Static {
    height: auto;
    padding: 0 1;
}

/* Kind badges in list items */
.kind-badge {
    width: 6;
    height: 1;
    content-align: center middle;
    text-style: bold;
    margin-right: 1;
    border: round var(--bg-panel);
}

.kind-badge.movie { background: var(--kind-movie); color: var(--bg-deep); }
.kind-badge.series { background: var(--kind-series); color: var(--bg-deep); }
.kind-badge.anime { background: var(--kind-anime); color: var(--fg-primary); }
.kind-badge.live { background: var(--kind-live); color: var(--fg-primary); }

/* ─── Poster art ─── */
#detail-poster {
    height: 18;
    width: 100%;
    content-align: center middle;
    background: var(--bg-surface);
    border: round var(--fg-dim);
    margin-bottom: 1;
    overflow: hidden;
}

#detail-poster > Static {
    width: 100%;
    height: 100%;
    background: var(--grad-panel);
}

/* Placeholder when no poster */
.poster-placeholder {
    color: var(--fg-muted);
    text-style: bold;
}

.poster-image {
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
    border: round var(--fg-dim);
}

/* ─── Detail panel content ─── */
#detail-title {
    text-style: bold;
    height: auto;
    margin-bottom: 1;
    background: var(--grad-primary);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    line-height: 1.2;
}

#detail-meta {
    color: var(--fg-secondary);
    height: auto;
    margin-bottom: 1;
    line-height: 1.5;
}

#detail-meta > Span {
    margin-right: 2;
}

.meta-year { color: var(--accent-gold); }
.meta-kind { color: var(--accent-cyan); }
.meta-source { color: var(--accent-magenta); }

#detail-genres {
    height: auto;
    margin-bottom: 1;
    color: var(--fg-muted);
}

.genre-tag {
    background: var(--bg-surface);
    color: var(--accent-orange);
    padding: 0 1;
    margin-right: 1;
    border: round var(--fg-dim);
    text-style: bold;
}

#detail-overview {
    height: 1fr;
    color: var(--fg-secondary);
    line-height: 1.4;
    overflow-y: auto;
    scrollbar-color: var(--accent-magenta);
    scrollbar-background: transparent;
    scrollbar-size: 1 1;
}

/* ─── Status line ─── */
#status-line {
    dock: bottom;
    height: 1;
    padding: 0 2;
    background: var(--bg-panel);
    color: var(--fg-muted);
    border-top: thick var(--fg-dim);
    text-style: italic;
}

/* ─── Modals (Episode / Quality pickers) ─── */
ModalScreen {
    background: rgba(13, 13, 26, 0.85);
    animation: fade-in 200ms ease-out;
}

#episode-list-container,
#quality-list-container {
    width: 70%;
    max-width: 100;
    height: 70%;
    max-height: 30;
    margin: 4 8;
    border: thick var(--accent-cyan);
    background: var(--grad-panel);
    animation: slide-up 300ms ease-out;
    box-shadow:
        0 0 20 var(--accent-cyan) 40%,
        0 4 32 rgba(0, 0, 0, 0.5);
}

#episode-title,
#quality-title {
    height: 1;
    padding: 0 2;
    background: var(--grad-primary);
    color: var(--bg-deep);
    text-style: bold;
    border-bottom: thick var(--accent-cyan);
}

#episode-list-container ListView,
#quality-list-container ListView {
    background: var(--bg-surface);
    scrollbar-color: var(--accent-cyan);
    scrollbar-background: transparent;
    scrollbar-size: 1 1;
    height: 1fr;
}

#episode-list-container ListItem,
#quality-list-container ListItem {
    height: auto;
    min-height: 2;
    padding: 0 2;
    margin: 0 1;
    border-left: thick transparent;
    transition: background 150ms, border 150ms;
}

#episode-list-container ListItem.--highlight,
#quality-list-container ListItem.--highlight {
    background: var(--bg-boost);
    border-left: thick var(--accent-gold);
}

/* Quality tags */
.quality-tag {
    background: var(--bg-panel);
    color: var(--accent-green);
    padding: 0 1;
    margin-right: 1;
    border: round var(--fg-dim);
    text-style: bold;
}

.quality-tag.direct { color: var(--accent-cyan); }
.quality-tag.magnet { color: var(--accent-orange); }
.quality-tag.debrid { color: var(--accent-gold); background: linear-gradient(90deg, var(--bg-panel), var(--accent-gold) 20%); }

/* ─── Scrollbars (global) ─── */
ScrollBar {
    background: var(--bg-surface);
}

ScrollBar > Slider {
    background: var(--accent-cyan);
    border: round var(--accent-cyan);
    min-height: 20;
}

ScrollBar > Slider:hover {
    background: var(--accent-magenta);
    border: round var(--accent-magenta);
}

ScrollBar > Button {
    display: none;
}

/* ─── Toast / Notifications ─── */
Toast {
    background: var(--grad-panel);
    border: round var(--accent-cyan);
    color: var(--fg-primary);
    padding: 1 2;
    box-shadow: 0 4 24 rgba(0, 255, 255, 0.3);
}

/* ─── Input dialogs ─── */
Input {
    border: thick var(--bg-panel);
    background: var(--bg-surface);
    transition: border 150ms, box-shadow 150ms;
}

Input:focus {
    border: thick var(--accent-cyan);
    box-shadow: 0 0 4 var(--accent-cyan);
}

/* ─── Button ─── */
Button {
    background: var(--bg-panel);
    color: var(--fg-primary);
    border: round var(--fg-dim);
    padding: 0 3;
    margin: 0 1;
    transition: all 150ms;
}

Button:hover {
    background: var(--accent-cyan);
    color: var(--bg-deep);
    border: round var(--accent-cyan);
    text-style: bold;
}

Button:focus {
    border: thick var(--accent-gold);
}

/* ─── Progress bar ─── */
ProgressBar {
    background: var(--bg-surface);
    border: round var(--fg-dim);
}

ProgressBar > Bar {
    background: var(--grad-primary);
    border: round var(--accent-cyan);
}

/* ─── DataTable (if used) ─── */
DataTable {
    background: var(--bg-surface);
}

DataTable > .datatable--header {
    background: var(--bg-panel);
    color: var(--accent-cyan);
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: var(--bg-boost);
}

/* ─── Responsive adjustments ─── */
@media (max-width: 100) {
    #search-body {
        layout: vertical;
    }

    .results-panel {
        width: 100%;
        height: 1fr;
    }

    #detail-panel {
        width: 100%;
        min-width: 0;
        height: 40%;
        margin: 0 2 2 2;
    }
}

/* ─── Reduced motion ─── */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
"""

# Sentinel class: truthy for 'or' check, but iterates to empty list
class _EmptyCssPath(list):
    def __bool__(self) -> bool:
        return True  # Survives Textual's 'css_path or self.CSS_PATH' check

    def __iter__(self):
        return iter([])  # But yields no paths


class TorrentioTuiApp(App):
    CSS_PATH = []  # Empty list disables auto-discovery (None triggers it)
    CSS = TORRENTIO_CSS  # Embedded CSS via class variable (standard Textual way)
    TITLE = "🎬 Torrentio TUI"
    SUB_TITLE = "search · stream · watch"

    def __init__(self, sources: list[Source], config: Config) -> None:
        # Pass truthy-but-empty sentinel to bypass Textual's 'or' logic
        super().__init__(css_path=_EmptyCssPath())
        self.sources = sources
        self.config = config

    def on_mount(self) -> None:
        self.register_theme(TORRENTIO_THEME)
        self.theme = "torrentio"
        self.push_screen(MainScreen(self.sources, self.config))