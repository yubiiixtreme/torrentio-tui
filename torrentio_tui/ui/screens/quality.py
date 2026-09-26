from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from torrentio_tui.models import StreamLink

_QUALITY_COLOR = (
    ("2160", "#F5C518"),
    ("4K", "#F5C518"),
    ("1080", "cyan"),
    ("720", "#2ECC71"),
    ("480", "#E67E22"),
    ("CAM", "#E74C3C"),
    ("SCR", "#E74C3C"),
)


def _quality_color(label: str) -> str:
    upper = label.upper()
    for token, color in _QUALITY_COLOR:
        if token in upper:
            return color
    return "white"


class StreamPicked(ListItem):
    def __init__(self, stream: StreamLink) -> None:
        color = _quality_color(stream.quality)
        icon = "📡" if stream.is_live else "🎞"
        label = f"{icon} [bold {color}]{stream.quality}[/bold {color}]"
        if stream.is_live:
            label += " [dim](live)[/dim]"
        super().__init__(Static(label))
        self.stream = stream


class QualityScreen(ModalScreen[StreamLink | None]):
    """Pick a stream quality. Dismisses with the chosen StreamLink, or None."""

    BINDINGS = [("escape", "cancel", "Back")]

    def __init__(self, streams: list[StreamLink]) -> None:
        super().__init__()
        self.streams = streams

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="quality-list-container"):
            yield Static("Choose a stream", id="quality-title")
            yield ListView(*[StreamPicked(s) for s in self.streams])
        yield Footer()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        if self.streams:
            list_view.index = 0
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, StreamPicked):
            self.dismiss(item.stream)

    def action_cancel(self) -> None:
        self.dismiss(None)
