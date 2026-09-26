from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

KEYBINDINGS = (
    ("↑ / ↓", "Move selection"),
    ("Enter", "Play selected title / episode / stream"),
    ("Tab", "Switch focus between search box, results, detail panel"),
    ("l", "Save or unsave the highlighted title in your Library"),
    ("d", "Download the highlighted title (needs yt-dlp)"),
    ("i", "Show quick info for the highlighted title"),
    ("?", "Show this help"),
    ("Esc", "Close a picker / this help screen"),
    ("q", "Quit"),
)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss_help", "Close"), ("question_mark", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="help-container"):
            yield Static("⌨  Keybindings", id="help-title")
            lines = "\n".join(f"[bold]{key:<8}[/bold]  {desc}" for key, desc in KEYBINDINGS)
            yield Static(lines, id="help-body", markup=True)
        yield Footer()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
