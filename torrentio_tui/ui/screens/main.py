from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
)

from torrentio_tui.config import Config
from torrentio_tui.history import HistoryStore
from torrentio_tui.library import LibraryStore
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.player.registry import get_player
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.ui.screens.episodes import EpisodeScreen
from torrentio_tui.ui.screens.help import HelpScreen
from torrentio_tui.ui.screens.quality import QualityScreen

KIND_STYLE: dict[MediaKind, tuple[str, str, str]] = {
    MediaKind.MOVIE: ("🎬", "cyan", "MOVIE"),
    MediaKind.SERIES: ("📺", "green", "SERIES"),
    MediaKind.ANIME: ("🎴", "magenta", "ANIME"),
    MediaKind.LIVE: ("📡", "red", "LIVE"),
}


def _kind_style(kind: MediaKind) -> tuple[str, str, str]:
    return KIND_STYLE.get(kind, ("🎞", "white", kind.value.upper()))


class ResultItem(ListItem):
    def __init__(self, item: SearchResult) -> None:
        icon, color, label = _kind_style(item.kind)
        year = f" [dim]({item.year})[/dim]" if item.year else ""
        line1 = f"{icon} [bold]{item.title}[/bold]{year}"

        overview = (item.overview or "").strip()
        snippet = f"{overview[:100]}…" if len(overview) > 100 else overview
        line2 = f"   [{color}]{label}[/{color}] [dim]· {item.source_id}[/dim]"
        if snippet:
            line2 += f"  [dim]{snippet}[/dim]"

        super().__init__(
            Static(f"{line1}\n{line2}", markup=True), classes=f"kind-{item.kind.value}"
        )
        self.item = item


class HistoryItem(ListItem):
    def __init__(self, label: str, item_id: str, source_id: str) -> None:
        super().__init__(Static(label))
        self.item_id = item_id
        self.source_id = source_id


class MainScreen(Screen):
    BINDINGS = [
        ("l", "toggle_library", "Save/unsave"),
        ("d", "download", "Download"),
        ("i", "info", "Info"),
        ("question_mark", "help", "Help"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, sources: list[Source], config: Config) -> None:
        super().__init__()
        self.sources = sources
        self.config = config
        self.history = HistoryStore()
        self.library = LibraryStore()
        self._last_results: list[SearchResult] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="search"):
            with TabPane("🔍  Search", id="search"), Vertical():
                yield Input(placeholder="Search movies, series, anime...", id="search-input")
                yield LoadingIndicator(id="search-loading")
                with Horizontal(id="search-body"):
                    yield ListView(id="search-results", classes="results-panel")
                    yield self._build_detail_panel()
            with TabPane("⏯  Continue Watching", id="continue"):
                yield ListView(id="continue-results", classes="results-panel")
            with TabPane("❤️  Library", id="library"):
                yield ListView(id="library-results", classes="results-panel")
        yield Footer()

    def _build_detail_panel(self) -> Vertical:
        return Vertical(
            Static(id="detail-poster"),
            Static(id="detail-title"),
            Static(id="detail-meta"),
            Static(id="detail-genres"),
            Static(id="detail-overview"),
            id="detail-panel",
        )

    def on_mount(self) -> None:
        self._show_detail(None)
        self.query_one("#search-loading", LoadingIndicator).display = False
        self.query_one("#search-input", Input).focus()

    def on_screen_resume(self) -> None:
        self.refresh_continue_watching()
        self.refresh_library()

    def refresh_continue_watching(self) -> None:
        list_view = self.query_one("#continue-results", ListView)
        list_view.clear()
        for entry in self.history.recent():
            label = entry.title
            if entry.episode_label:
                label += f" — {entry.episode_label}"
            pct = ""
            if entry.duration_seconds:
                pct = f" ({entry.position_seconds / entry.duration_seconds:.0%})"
            list_view.append(HistoryItem(label + pct, entry.item_id, entry.source_id))

    def refresh_library(self) -> None:
        list_view = self.query_one("#library-results", ListView)
        list_view.clear()
        for item in self.library.all():
            list_view.append(ResultItem(item))

    def _show_detail(self, item: SearchResult | None) -> None:
        poster = self.query_one("#detail-poster", Static)
        title = self.query_one("#detail-title", Static)
        meta = self.query_one("#detail-meta", Static)
        genres = self.query_one("#detail-genres", Static)
        overview = self.query_one("#detail-overview", Static)

        if item is None:
            poster.styles.border = ("round", "gray")
            poster.update("🍿")
            title.update("[dim]Select a title to preview[/dim]")
            meta.update("")
            genres.update("")
            overview.update("[dim]Use ↑/↓ to browse results. Enter to play.[/dim]")
            return

        icon, color, label = _kind_style(item.kind)
        poster.styles.border = ("round", color)
        poster.update(f"{icon}\n[b]{label}[/b]")

        title.update(f"[bold]{item.title}[/bold]")
        year = str(item.year) if item.year else "—"
        meta.update(f"[{color}]{label}[/{color}]  ·  {year}  ·  [dim]{item.source_id}[/dim]")
        genres.update(f"[dim]{', '.join(item.genres)}[/dim]" if item.genres else "")
        overview.update(
            item.overview.strip() if item.overview else "[dim]No synopsis available.[/dim]"
        )

    def show_error_detail(self, message: str) -> None:
        self.query_one("#detail-overview", Static).update(f"[red]{message}[/red]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.run_search(event.value)

    @work(exclusive=True)
    async def run_search(self, query: str) -> None:
        loading = self.query_one("#search-loading", LoadingIndicator)
        loading.display = True
        try:
            results: list[SearchResult] = []
            errors: list[str] = []
            for source in self.sources:
                try:
                    results.extend(source.search(query))
                except SourceError as exc:
                    errors.append(str(exc))

            self._last_results = results
            list_view = self.query_one("#search-results", ListView)
            list_view.clear()
            for item in results:
                list_view.append(ResultItem(item))

            if results:
                list_view.index = 0
                list_view.focus()
                self._show_detail(results[0])
            else:
                self._show_detail(None)

            if errors:
                self.app.notify(" | ".join(errors), severity="error", timeout=8)
            elif not results:
                self.app.notify("No results found", severity="warning")
        finally:
            loading.display = False

    def _find_source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id), None)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "search-results":
            return
        item = event.item
        self._show_detail(item.item if isinstance(item, ResultItem) else None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ResultItem):
            self.open_item(item.item)
        elif isinstance(item, HistoryItem):
            self.resume_history_item(item)

    def action_toggle_library(self) -> None:
        results_list = self.query_one("#search-results", ListView)
        highlighted = results_list.highlighted_child
        if isinstance(highlighted, ResultItem):
            if self.library.contains(highlighted.item):
                self.library.remove(highlighted.item)
                self.app.notify(f"Removed from library: {highlighted.item.title}")
            else:
                self.library.add(highlighted.item)
                self.app.notify(f"Saved to library: {highlighted.item.title}")
            self.refresh_library()

    def action_info(self) -> None:
        results_list = self.query_one("#search-results", ListView)
        highlighted = results_list.highlighted_child
        if isinstance(highlighted, ResultItem):
            item = highlighted.item
            genres = ", ".join(item.genres) if item.genres else "—"
            self.app.notify(
                f"{item.title} ({item.year or '—'})\n"
                f"Kind: {item.kind.value}  ·  Genres: {genres}\n"
                f"Source: {item.source_id}  ·  ID: {item.id}",
                title="Info",
                timeout=8,
            )

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_download(self) -> None:
        results_list = self.query_one("#search-results", ListView)
        highlighted = results_list.highlighted_child
        if not isinstance(highlighted, ResultItem):
            self.app.notify("Highlight a title first", severity="warning")
            return
        self._download_item(highlighted.item)

    @work(exclusive=True)
    async def _download_item(self, item: SearchResult) -> None:
        source = self._find_source(item.source_id)
        if source is None:
            return

        episode: Episode
        if item.kind in (MediaKind.SERIES, MediaKind.ANIME):
            episodes = source.get_episodes(item)
            picked = await self.app.push_screen_wait(EpisodeScreen(episodes))
            if picked is None:
                return
            episode = picked
        else:
            episode = Episode(id=item.id, title=item.title)

        try:
            streams = source.get_streams(item, episode)
        except SourceError as exc:
            self.app.notify(str(exc), severity="error", timeout=10)
            return

        if not streams:
            self.app.notify("No downloadable streams found", severity="warning")
            return

        stream = (
            streams[0]
            if len(streams) == 1
            else await self.app.push_screen_wait(QualityScreen(streams))
        )
        if stream is None:
            return

        self._run_download(item, episode, stream)

    @work(exclusive=True, thread=True)
    def _run_download(self, item: SearchResult, episode: Episode, stream: StreamLink) -> None:
        from torrentio_tui.downloads import DownloadError, download, is_available

        if not is_available():
            self.app.call_from_thread(
                self.app.notify,
                "yt-dlp is not installed — install it to enable downloads.",
                severity="error",
                timeout=10,
            )
            return

        title = f"{item.title} - {episode.title}" if episode.title != item.title else item.title
        self.app.call_from_thread(self.app.notify, f"Downloading: {title}", severity="information")
        try:
            dest = download(stream, title, Path(self.config.downloads.directory))
        except DownloadError as exc:
            self.app.call_from_thread(self.app.notify, str(exc), severity="error", timeout=10)
            return
        self.app.call_from_thread(
            self.app.notify, f"Saved to {dest}", severity="information", timeout=8
        )

    @work(exclusive=True)
    async def open_item(self, item: SearchResult) -> None:
        source = self._find_source(item.source_id)
        if source is None:
            return

        episode: Episode
        if item.kind in (MediaKind.SERIES, MediaKind.ANIME):
            episodes = source.get_episodes(item)
            picked = await self.app.push_screen_wait(EpisodeScreen(episodes))
            if picked is None:
                return
            episode = picked
        else:
            episode = Episode(id=item.id, title=item.title)

        try:
            streams = source.get_streams(item, episode)
        except SourceError as exc:
            self.app.notify(str(exc), severity="error", timeout=10)
            self.show_error_detail(str(exc))
            return

        if not streams:
            self.app.notify("No playable streams found", severity="warning")
            self.show_error_detail("No playable streams found for this title/episode.")
            return

        stream = (
            streams[0]
            if len(streams) == 1
            else await self.app.push_screen_wait(QualityScreen(streams))
        )
        if stream is None:
            return

        self.play_stream(item, episode, stream)

    def resume_history_item(self, hist_item: HistoryItem) -> None:
        source = self._find_source(hist_item.source_id)
        if source is None:
            return
        entry = self.history.get(hist_item.source_id, hist_item.item_id)
        if entry is None:
            return
        result = SearchResult(
            id=hist_item.item_id,
            title=entry.title,
            kind=MediaKind.MOVIE,
            source_id=hist_item.source_id,
        )
        episode = Episode(id=hist_item.item_id, title=entry.title)
        try:
            streams = source.get_streams(result, episode)
        except SourceError as exc:
            self.app.notify(str(exc), severity="error", timeout=10)
            return
        if streams:
            self.play_stream(result, episode, streams[0], resume_seconds=entry.position_seconds)

    def play_stream(
        self, item: SearchResult, episode: Episode, stream, resume_seconds: float = 0.0
    ) -> None:
        from torrentio_tui.player.torrent import TorrentStreamError

        player = get_player(self.config.player.backend)
        try:
            with self.app.suspend():
                player.play(stream, title=item.title, resume_seconds=resume_seconds)
        except TorrentStreamError as exc:
            self.app.notify(str(exc), severity="error", timeout=10)
            self.show_error_detail(str(exc))
            return
        except FileNotFoundError:
            message = f"Player '{self.config.player.backend}' not found — install mpv or vlc."
            self.app.notify(message, severity="error", timeout=10)
            self.show_error_detail(message)
            return

        self.history.record(
            item_id=item.id,
            source_id=item.source_id,
            title=item.title,
            episode_label=episode.title if episode.title != item.title else None,
            position_seconds=0.0,
            duration_seconds=None,
        )
        self.refresh_continue_watching()
