from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from torrentio_tui.config import get_language_config
from torrentio_tui.languages import SUBTITLE_LANGUAGE_CODES
from torrentio_tui.models import StreamLink
from torrentio_tui.player.torrent import is_torrent_link
from torrentio_tui.ui.widgets import VimListView

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

STREAM_ICONS = {
    "magnet": ("🧲", "MAGNET", "orange"),
    "debrid": ("⚡", "DEBRID", "gold"),
    "direct": ("📡", "DIRECT", "cyan"),
    "stream": ("🎞", "STREAM", "white"),
    "live": ("📺", "LIVE", "red"),
}


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
        return STREAM_ICONS["magnet"]
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
        return STREAM_ICONS["debrid"]
    if url.startswith(("http://", "https://")):
        return STREAM_ICONS["direct"] if not stream.is_live else STREAM_ICONS["live"]
    return STREAM_ICONS["stream"]


def _stream_rank(stream: StreamLink) -> int:
    """Order the quality picker so instant, seekable streams come first.

    Direct/debrid HTTP(S) starts playing from the current buffer right
    away and supports jumping to any timestamp; local files are next;
    torrent/magnet links (sequential download — playback can't skip
    ahead of the downloaded pieces) sink to the bottom. Stable, so
    sources keep their relative order within each tier.
    """
    url = stream.url.lower()
    if is_torrent_link(url):
        return 2
    if url.startswith(("http://", "https://")):
        return 0
    return 1


def ranked_streams(streams: list[StreamLink]) -> list[StreamLink]:
    """Sort streams direct-first (see `_stream_rank`). Used by the picker
    and by every auto-pick path so the default is always the fastest to
    start and seekable — including downloads, where a magnet first would
    just error out (yt-dlp can't fetch torrents)."""
    return sorted(streams, key=_stream_rank)


class StreamPicked(ListItem):
    def __init__(self, stream: StreamLink) -> None:
        from rich.markup import escape

        qcolor = _quality_color(stream.quality)
        sicon, stype, scolor = _stream_type(stream)

        sub_indicator = "  💬" if stream.subtitle_url else ""

        label = (
            f"{sicon}  [{scolor}]{stype}[/{scolor}]  "
            f"[bold {qcolor}]{escape(stream.quality)}[/bold {qcolor}]"
        )
        if stream.is_live:
            label += " [dim](live)[/dim]"
        label += sub_indicator
        super().__init__(Static(label, markup=True))
        self.stream = stream


class SubtitlePicked(ListItem):
    def __init__(self, lang_code: str, lang_name: str, is_selected: bool = False) -> None:
        marker = "✓ " if is_selected else "  "
        label = f"{marker}[bold]{lang_name}[/bold] [dim]({lang_code})[/dim]"
        super().__init__(Static(label, markup=True))
        self.lang_code = lang_code
        self.lang_name = lang_name


class QualityScreen(ModalScreen[StreamLink | None]):
    """Pick a stream quality. Dismisses with the chosen StreamLink, or None."""

    BINDINGS = [
        ("escape", "cancel", "Back"),
        ("s", "subtitles", "Subtitles"),
    ]

    def __init__(self, streams: list[StreamLink], lang_config=None) -> None:
        super().__init__()
        # Direct HTTP first (instant start + seeking), magnets last —
        # see _stream_rank. The auto-picked streams[0] elsewhere benefits too.
        self.streams = ranked_streams(streams)
        # Use the caller's shared language config when provided so the
        # subtitle picker actually affects playback (which reads
        # MainScreen.config.language). Fall back to a fresh load for
        # standalone use (tests, direct pushes).
        self.lang_config = lang_config if lang_config is not None else get_language_config()
        self.show_subtitles = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="quality-list-container"):
            yield Static("⚡  Choose Stream Quality  [dim](s=subtitles)[/dim]", id="quality-title")
            yield VimListView(*[StreamPicked(s) for s in self.streams])
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

    def action_subtitles(self) -> None:
        """Subtitle preference picker — the choice is moved to the top of
        the preferred-languages list for this session."""
        self.app.push_screen(SubtitleScreen(self.lang_config), callback=self._on_subtitle_picked)

    def _on_subtitle_picked(self, code: str | None) -> None:
        if not code:
            return
        prefs = [c for c in self.lang_config.subtitle_languages if c != code]
        self.lang_config.subtitle_languages = [code, *prefs]
        self.app.notify(f"Preferred subtitles: {code}", timeout=3)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SubtitleScreen(ModalScreen[str | None]):
    """Select subtitle language."""

    BINDINGS = [("escape", "cancel", "Back")]

    def __init__(self, lang_config) -> None:
        super().__init__()
        self.lang_config = lang_config

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="quality-list-container"):
            yield Static(
                "💬  Subtitle Languages  [dim](Enter to select, Esc to cancel)[/dim]",
                id="quality-title",
            )
            items = []
            for index, code in enumerate(self.lang_config.subtitle_languages):
                lang_name = self._get_lang_name(code)
                # Only the top preference gets the default check — the old
                # code compared each code against the very list it was
                # iterating, so *every* row showed ✓.
                items.append(SubtitlePicked(code, lang_name, is_selected=index == 0))
            yield VimListView(*items)
        yield Footer()

    def _get_lang_name(self, code: str) -> str:
        # SUBTITLE_LANGUAGE_CODES maps ISO-639-2/T code -> Language enum.
        lang = SUBTITLE_LANGUAGE_CODES.get(code)
        if lang is not None:
            return lang.name.replace("_", " ").title()
        return code.upper()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, SubtitlePicked):
            self.dismiss(item.lang_code)

    def action_cancel(self) -> None:
        self.dismiss(None)
