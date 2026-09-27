from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
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


class StreamPicked(ListItem):
    def __init__(self, stream: StreamLink, lang_config=None) -> None:
        qcolor = _quality_color(stream.quality)
        sicon, stype, scolor = _stream_type(stream)

        # Subtitle indicator
        sub_indicator = ""
        if stream.subtitle_url:
            sub_indicator = "  💬"

        # Language indicator
        lang_indicator = ""
        if stream.subtitle_url and lang_config:
            # Try to detect subtitle language
            lang_indicator = ""

        label = (
            f"{sicon}  [{scolor}]{stype}[/{scolor}]  "
            f"[bold {qcolor}]{stream.quality}[/bold {qcolor}]"
        )
        if stream.is_live:
            label += " [dim](live)[/dim]"
        label += sub_indicator + lang_indicator
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
        ("l", "language", "Language"),
    ]

    def __init__(self, streams: list[StreamLink]) -> None:
        super().__init__()
        self.streams = streams
        self.lang_config = get_language_config()
        self.show_subtitles = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="quality-list-container"):
            yield Static(
                "⚡  Choose Stream Quality  [dim](s=subtitles l=language)[/dim]", id="quality-title"
            )
            yield VimListView(*[StreamPicked(s, self.lang_config) for s in self.streams])
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
        """Toggle subtitle selection panel."""
        self.show_subtitles = not self.show_subtitles
        if self.show_subtitles:
            self.app.push_screen(SubtitleScreen(self.lang_config))

    def action_language(self) -> None:
        """Open language selection."""
        self.app.push_screen(LanguageScreen(self.lang_config))

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
            for code in self.lang_config.subtitle_languages:
                lang_name = self._get_lang_name(code)
                items.append(
                    SubtitlePicked(code, lang_name, code in self.lang_config.subtitle_languages)
                )
            yield VimListView(*items)
        yield Footer()

    def _get_lang_name(self, code: str) -> str:
        for lang in SUBTITLE_LANGUAGE_CODES:
            if lang.value == code:
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


class LanguageScreen(ModalScreen[str | None]):
    """Select UI language."""

    BINDINGS = [("escape", "cancel", "Back")]

    def __init__(self, lang_config) -> None:
        super().__init__()
        self.lang_config = lang_config

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="quality-list-container"):
            yield Static(
                "🌐  UI Language  [dim](Enter to select, Esc to cancel)[/dim]", id="quality-title"
            )
            items = []
            for lang in [
                ("en", "English"),
                ("es", "Spanish"),
                ("fr", "French"),
                ("de", "German"),
                ("it", "Italian"),
                ("pt", "Portuguese"),
                ("ru", "Russian"),
                ("zh", "Chinese"),
                ("ja", "Japanese"),
                ("ko", "Korean"),
                ("ar", "Arabic"),
                ("hi", "Hindi"),
                ("tr", "Turkish"),
                ("pl", "Polish"),
                ("nl", "Dutch"),
                ("sv", "Swedish"),
                ("no", "Norwegian"),
                ("da", "Danish"),
                ("fi", "Finnish"),
                ("cs", "Czech"),
                ("hu", "Hungarian"),
                ("ro", "Romanian"),
                ("bg", "Bulgarian"),
                ("hr", "Croatian"),
                ("sr", "Serbian"),
                ("uk", "Ukrainian"),
            ]:
                code, name = lang
                is_selected = code == self.lang_config.ui_language
                items.append(SubtitlePicked(code, name, is_selected))
            yield VimListView(*items)
        yield Footer()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, SubtitlePicked):
            self.dismiss(item.lang_code)

    def action_cancel(self) -> None:
        self.dismiss(None)
