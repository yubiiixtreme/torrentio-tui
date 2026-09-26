from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static, TabbedContent, TabPane

from torrentio_tui.config import Config
from torrentio_tui.history import HistoryStore
from torrentio_tui.library import LibraryStore
from torrentio_tui.models import Episode, MediaKind, SearchResult
from torrentio_tui.player.registry import get_player
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.ui.screens.episodes import EpisodeScreen
from torrentio_tui.ui.screens.quality import QualityScreen


class ResultItem(ListItem):
    def __init__(self, item: SearchResult) -> None:
        label = item.title
        if item.year:
            label += f" ({item.year})"
        label += f"  [{item.source_id}]"
        super().__init__(Static(label))
        self.item = item


class HistoryItem(ListItem):
    def __init__(self, label: str, item_id: str, source_id: str) -> None:
        super().__init__(Static(label))
        self.item_id = item_id
        self.source_id = source_id


class MainScreen(Screen):
    BINDINGS = [
        ("l", "toggle_library", "Save/unsave"),
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
            with TabPane("Search", id="search"):
                with Vertical():
                    yield Input(placeholder="Search titles...", id="search-input")
                    yield ListView(id="search-results")
            with TabPane("Continue Watching", id="continue"):
                yield ListView(id="continue-results")
            with TabPane("Library", id="library"):
                yield ListView(id="library-results")
        yield Footer()
        yield Static(id="status-line")

    def on_screen_resume(self) -> None:
        self.refresh_continue_watching()
        self.refresh_library()

    def refresh_continue_watching(self) -> None:
        list_view = self.query_one("#continue-results", ListView)
        list_view.clear()
        for entry in self.history.recent():
            label = entry.title
            if entry.episode_label:
                label += f" - {entry.episode_label}"
            pct = ""
            if entry.duration_seconds:
                pct = f" ({entry.position_seconds / entry.duration_seconds:.0%})"
            list_view.append(HistoryItem(label + pct, entry.item_id, entry.source_id))

    def refresh_library(self) -> None:
        list_view = self.query_one("#library-results", ListView)
        list_view.clear()
        for item in self.library.all():
            list_view.append(ResultItem(item))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.run_search(event.value)

    @work(exclusive=True)
    async def run_search(self, query: str) -> None:
        status = self.query_one("#status-line", Static)
        status.update(f"Searching for '{query}'...")

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

        if errors:
            status.update(" | ".join(errors))
        else:
            status.update(f"{len(results)} result(s)")

    def _find_source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id), None)

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
            else:
                self.library.add(highlighted.item)
            self.refresh_library()

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
            self.query_one("#status-line", Static).update(str(exc))
            return

        if not streams:
            self.query_one("#status-line", Static).update("No playable streams found")
            return

        stream = streams[0] if len(streams) == 1 else await self.app.push_screen_wait(QualityScreen(streams))
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
        result = SearchResult(id=hist_item.item_id, title=entry.title, kind=MediaKind.MOVIE, source_id=hist_item.source_id)
        episode = Episode(id=hist_item.item_id, title=entry.title)
        try:
            streams = source.get_streams(result, episode)
        except SourceError as exc:
            self.query_one("#status-line", Static).update(str(exc))
            return
        if streams:
            self.play_stream(result, episode, streams[0], resume_seconds=entry.position_seconds)

    def play_stream(self, item: SearchResult, episode: Episode, stream, resume_seconds: float = 0.0) -> None:
        from torrentio_tui.player.torrent import TorrentStreamError

        player = get_player(self.config.player.backend)
        try:
            with self.app.suspend():
                player.play(stream, title=item.title, resume_seconds=resume_seconds)
        except TorrentStreamError as exc:
            self.query_one("#status-line", Static).update(str(exc))
            return
        except FileNotFoundError:
            self.query_one("#status-line", Static).update(
                f"Player '{self.config.player.backend}' not found — install mpv or vlc."
            )
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
