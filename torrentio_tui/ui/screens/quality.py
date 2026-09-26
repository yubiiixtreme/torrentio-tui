from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from torrentio_tui.models import StreamLink
from torrentio_tui.player.torrent import is_torrent_link

_QUALITY_COLOR = (
    ("2160", "gold"),
    ("4K", "gold"),
    ("1080", "cyan"),
    ("720", "green"),
    ("480", "orange"),
    ("CAM", "red"),
    ("SCR", "red"),
    ("TS", "red"),
)


def _quality_color(label: str) -> str:
    upper = label.upper()
    for token, color in _QUALITY_COLOR:
        if token in upper:
            return color
    return "white"


def _stream_type(stream: StreamLink) -> tuple[str, str, str]:
    """Return (icon, type_label, type_color) for the stream."""
    url = stream.url.lower()
    if is_torrent_link(url):
        return "🧲", "MAGNET", "orange"
    if any(
        d in url
        for d in (
            "realdebrid",
            "alldebrid",
            "premiumize",
            "debridlink",
            "offcloud",
            "put.io",
            "torbox",
        )
    ):
        return "⚡", "DEBRID", "gold"
    if url.startswith(("http://", "https://")):
        return "📡", "DIRECT", "cyan"
    return "🎞", "STREAM", "white"


class StreamPicked(ListItem):
    def __init__(self, stream: StreamLink) -> None:
        qcolor = _quality_color(stream.quality)
        sicon, stype, scolor = _stream_type(stream)
        label = (
            f"{sicon}  [{scolor}]{stype}[/{scolor}]  "
            f"[bold {qcolor}]{stream.quality}[/bold {qcolor}]"
        )
        if stream.is_live:
            label += " [dim](live)[/dim]"
        if stream.subtitle_url:
            label += "  💬"
        super().__init__(Static(label, markup=True))
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
            yield Static("⚡  Choose Stream Quality", id="quality-title")
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
