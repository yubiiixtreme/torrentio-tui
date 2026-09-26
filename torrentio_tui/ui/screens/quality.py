from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from torrentio_tui.models import StreamLink


class StreamPicked(ListItem):
    def __init__(self, stream: StreamLink) -> None:
        label = stream.quality
        if stream.is_live:
            label += " (live)"
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
            yield ListView(*[StreamPicked(s) for s in self.streams])
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, StreamPicked):
            self.dismiss(item.stream)

    def action_cancel(self) -> None:
        self.dismiss(None)
