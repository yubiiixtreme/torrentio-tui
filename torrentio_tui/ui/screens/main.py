from __future__ import annotations

import asyncio
import re
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    LoadingIndicator,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from torrentio_tui.config import Config
from torrentio_tui.history import HistoryStore
from torrentio_tui.images import IMAGES_AVAILABLE, PosterWidget, download_image
from torrentio_tui.library import LibraryStore
from torrentio_tui.models import Episode, MediaKind, SearchResult, StreamLink
from torrentio_tui.player.registry import get_player
from torrentio_tui.sources.base import Source, SourceError
from torrentio_tui.ui.screens.episodes import EpisodeScreen
from torrentio_tui.ui.screens.help import HelpScreen
from torrentio_tui.ui.screens.quality import QualityScreen
from torrentio_tui.ui.widgets import VimListView

KIND_STYLE: dict[MediaKind, tuple[str, str, str]] = {
    MediaKind.MOVIE: ("🎬", "cyan", "MOVIE"),
    MediaKind.SERIES: ("📺", "green", "SERIES"),
    MediaKind.ANIME: ("🎴", "magenta", "ANIME"),
    MediaKind.LIVE: ("📡", "red", "LIVE"),
}


def _kind_style(kind: MediaKind) -> tuple[str, str, str]:
    return KIND_STYLE.get(kind, ("🎞", "white", kind.value.upper()))


def _source_color(source_id: str) -> str:
    colors = {
        "stremio": "yellow",
        "mediafusion": "green",
        "comet": "gold",
        "aiostreams": "gold",
        "stremthru": "cyan",
        "jackettio": "orange",
        "deflix": "purple",
        "stremify": "magenta",
        "knightcrawler": "blue",
        "torrentio-selfhost": "magenta",
        "yts": "lime",
        "tvmaze": "dodger_blue",
        "jikan": "pink",
        "kitsu": "orange",
        "iptv": "red",
        "anilist": "cyan",
        "nyaa": "orange",
        "subsplease": "purple",
        "local": "gray",
        "stremio-adult": "red",
        "hanime": "magenta",
        "nhentai": "pink",
        "rule34": "red",
        "eztv-rss": "orange",
        "torrentgalaxy": "gold",
        "magnetdl": "cyan",
        "vumoo": "green",
        "solarmovie": "green",
        "stremio-community": "magenta",
        "superstream": "cyan",
        "torrentio-cloud": "magenta",
        "limetorrents": "lime",
        "torrentdownloads": "orange",
        "glodls": "gold",
        "iptv-org": "red",
        "anidex": "cyan",
        "animetosho": "purple",
        "tokyotoshokan": "pink",
        "thepiratebay": "brown",
        "rarbg-mirror": "orange",
        "nyaa-torrents": "orange",
        "ehentai": "red",
        "hitomila": "magenta",
        "hentaihaven": "pink",
    }
    return colors.get(source_id, "white")


#: Year buckets for the ⩔ funnel filter.
YEAR_OPTIONS: tuple[str, ...] = (
    "Any year",
    "2026",
    "2025",
    "2024",
    "2020s",
    "2010s",
    "2000s",
    "Classic (<2000)",
)

#: Sort orders for the ⩔ funnel filter.
SORT_OPTIONS: tuple[str, ...] = (
    "Relevance",
    "Newest first",
    "Oldest first",
    "Title A–Z",
)


def _year_matches(year: int | None, bucket: str) -> bool:
    if bucket == "Any year":
        return True
    if year is None:
        return False
    if bucket == "2020s":
        return 2020 <= year <= 2029
    if bucket == "2010s":
        return 2010 <= year <= 2019
    if bucket == "2000s":
        return 2000 <= year <= 2009
    if bucket == "Classic (<2000)":
        return year < 2000
    try:
        return year == int(bucket)
    except ValueError:
        return True


def apply_result_filters(
    results: list[SearchResult],
    *,
    kind: str = "All",
    category: str = "All",
    genre: str = "",
    year: str = "Any year",
    sort: str = "Relevance",
) -> list[SearchResult]:
    """Funnel-filter a result set client-side (instant, no re-search).

    `kind` is a MediaKind value title ("Movie"/"Series"/...) or "All";
    `category` is a registry category label or "All"; `genre` matches
    case-insensitively against genres, title and overview.
    """
    from torrentio_tui.sources.registry import CATEGORIES

    label_to_id = {label: cid for cid, (label, _) in CATEGORIES.items()}
    target_kind = kind.lower() if kind != "All" else None
    target_category = label_to_id.get(category) if category != "All" else None
    genre_q = genre.strip().lower()

    filtered: list[SearchResult] = []
    for item in results:
        if target_kind and item.kind.value != target_kind:
            continue
        if target_category:
            source_cat = _source_category(item.source_id)
            if source_cat != target_category:
                continue
        if genre_q:
            haystack = " ".join([item.title, item.overview or "", *item.genres]).lower()
            if genre_q not in haystack:
                continue
        if not _year_matches(item.year, year):
            continue
        filtered.append(item)

    if sort == "Newest first":
        filtered.sort(key=lambda r: (r.year is None, -(r.year or 0)))
    elif sort == "Oldest first":
        filtered.sort(key=lambda r: (r.year is None, r.year or 0))
    elif sort == "Title A–Z":
        filtered.sort(key=lambda r: r.title.lower())
    return filtered


def _source_category(source_id: str) -> str:
    from torrentio_tui.sources.registry import _AVAILABLE

    cls = _AVAILABLE.get(source_id)
    return getattr(cls, "category", "streams") if cls is not None else "streams"


#: yt-dlp's own progress line, e.g. "[download]  42.3% of  700.00MiB at
#: 5.00MiB/s ETA 00:30" -- speed/ETA are absent on the final 100% line.
_DOWNLOAD_PROGRESS_RE = re.compile(
    r"\[download\]\s+(?P<pct>\d{1,3}(?:\.\d)?)%"
    r"(?:.*?at\s+(?P<speed>[\d.]+\S*iB/s))?"
    r"(?:.*?ETA\s+(?P<eta>[\d:]+))?"
)


def _format_download_progress(title: str, line: str) -> str | None:
    match = _DOWNLOAD_PROGRESS_RE.search(line)
    if match is None:
        return None
    parts = [f"⏳ {title} — {match['pct']}%"]
    if match["speed"]:
        parts.append(match["speed"])
    if match["eta"]:
        parts.append(f"ETA {match['eta']}")
    return "  ".join(parts)


def _format_playback_error(error: Exception, backend: str) -> str:
    from textual.app import SuspendNotSupported

    from torrentio_tui.player.torrent import TorrentStreamError

    if isinstance(error, TorrentStreamError):
        return str(error)
    if isinstance(error, SuspendNotSupported):
        return (
            "This terminal doesn't support suspending the app for playback "
            "(needed to hand the terminal to mpv/vlc) — try a different "
            "terminal emulator."
        )
    if isinstance(error, OSError):
        return f"Player '{backend}' not found — install mpv or vlc."
    return f"Playback failed ({type(error).__name__}): {error}"


class ResultItem(ListItem):
    def __init__(self, item: SearchResult) -> None:
        icon, color, label = _kind_style(item.kind)
        year = f" [dim]({item.year})[/dim]" if item.year else ""
        line1 = f"{icon} [bold]{item.title}[/bold]{year}"

        source_color = _source_color(item.source_id)
        line2 = f"   [{color}]{label}[/{color}] [dim]·[/dim] [{source_color}]{item.source_id}[/{source_color}]"
        genre_str = ", ".join(item.genres[:4])
        if genre_str:
            line2 += f" [dim]· {genre_str}[/dim]"

        lines = [line1, line2]
        overview = (item.overview or "").strip().replace("\n", " ")
        if overview:
            snippet = f"{overview[:120]}…" if len(overview) > 120 else overview
            lines.append(f"   [dim]{snippet}[/dim]")

        super().__init__(Static("\n".join(lines), markup=True), classes=f"kind-{item.kind.value}")
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
        ("t", "cycle_theme", "Theme"),
        ("s", "sources", "Sources"),
        ("f", "toggle_filters", "Filters"),
        ("g", "settings", "Settings"),
        ("slash", "focus_search", "Search"),
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
        self._pending_poster_url: str | None = None
        self._trending_loaded = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="download-status", classes="download-status")
        with TabbedContent(initial="search"):
            with TabPane("🔍  Search", id="search"), Vertical():
                with Horizontal(id="search-row"):
                    yield Input(
                        placeholder="Search movies, series, anime... (Enter to search)",
                        id="search-input",
                    )
                    yield Button("⩔ Filters", id="filter-toggle", variant="default")
                yield self._build_filter_bar()
                yield LoadingIndicator(id="search-loading")
                with Horizontal(id="search-body"):
                    yield VimListView(id="search-results", classes="results-panel")
                    yield self._build_detail_panel()
            with TabPane("🔥  Trending", id="trending"), Vertical():
                yield Static(
                    "Top movies & series right now — Enter to play, l to save",
                    id="trending-hint",
                )
                yield LoadingIndicator(id="trending-loading")
                yield VimListView(id="trending-results", classes="results-panel")
            with TabPane("⏯  Continue Watching", id="continue"):
                yield VimListView(id="continue-results", classes="results-panel")
            with TabPane("❤️  Library", id="library"):
                yield VimListView(id="library-results", classes="results-panel")
            with TabPane("🔌  Sources", id="sources"):
                yield VimListView(id="sources-list", classes="results-panel")
        yield Footer()

    def _build_filter_bar(self) -> Horizontal:
        """The ⩔ funnel bar: kind / category / genre / year / sort.

        Everything filters the already-fetched results client-side, so
        the funnel is instant — no waiting on the network per tweak.
        """
        from torrentio_tui.models import MediaKind
        from torrentio_tui.sources.registry import CATEGORIES

        kind_options = ["All"] + [k.value.title() for k in MediaKind]
        category_options = ["All"] + [label for label, _ in CATEGORIES.values()]

        return Horizontal(
            Static("[bold]⩔[/bold]", classes="filter-label"),
            Select(
                [(opt, opt) for opt in kind_options],
                value="All",
                id="filter-kind",
                allow_blank=False,
            ),
            Select(
                [(opt, opt) for opt in category_options],
                value="All",
                id="filter-category",
                allow_blank=False,
            ),
            Input(placeholder="Genre…", id="filter-genre"),
            Select(
                [(opt, opt) for opt in YEAR_OPTIONS],
                value=YEAR_OPTIONS[0],
                id="filter-year",
                allow_blank=False,
            ),
            Select(
                [(opt, opt) for opt in SORT_OPTIONS],
                value=SORT_OPTIONS[0],
                id="filter-sort",
                allow_blank=False,
            ),
            Static("", id="filter-count", classes="filter-count"),
            Button("Clear", id="filter-clear", variant="default"),
            id="filter-bar",
            classes="filter-bar",
        )

    def _build_detail_panel(self) -> Vertical:
        return Vertical(
            PosterWidget(id="detail-poster"),
            Static(id="detail-title"),
            Static(id="detail-meta"),
            Static(id="detail-badges"),
            Static(id="detail-genres"),
            Static(id="detail-overview"),
            Static(id="detail-actions"),
            Static(id="detail-source"),
            id="detail-panel",
        )

    def on_mount(self) -> None:
        self._show_detail(None)
        self.query_one("#search-loading", LoadingIndicator).display = False
        self.query_one("#trending-loading", LoadingIndicator).display = False
        self.query_one("#download-status", Static).display = False
        self.refresh_continue_watching()
        self.refresh_library()
        self._populate_sources_list()
        self._update_filter_count(0, 0)
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
        if len(list_view.children) > 0:
            list_view.index = 0

    def refresh_library(self) -> None:
        list_view = self.query_one("#library-results", ListView)
        list_view.clear()
        for item in self.library.all():
            list_view.append(ResultItem(item))
        if len(list_view.children) > 0:
            list_view.index = 0

    def _show_detail(self, item: SearchResult | None, position: str = "") -> None:
        poster = self.query_one("#detail-poster", PosterWidget)
        title = self.query_one("#detail-title", Static)
        meta = self.query_one("#detail-meta", Static)
        badges = self.query_one("#detail-badges", Static)
        genres = self.query_one("#detail-genres", Static)
        overview = self.query_one("#detail-overview", Static)
        actions = self.query_one("#detail-actions", Static)
        source = self.query_one("#detail-source", Static)

        if item is None:
            poster.show_fallback("🍿")
            title.update("[bold]No title selected[/bold]")
            meta.update("[dim]Search something to fill this panel[/dim]")
            badges.update("")
            genres.update("")
            overview.update(
                "[dim]↑/↓ or j/k to browse · Enter to play · "
                "f for the ⩔ funnel · g for settings[/dim]"
            )
            actions.update("")
            source.update("")
            return

        icon, color, label = _kind_style(item.kind)
        poster.show_fallback(icon, color)
        self._pending_poster_url = item.poster_url
        if item.poster_url and IMAGES_AVAILABLE:
            self._load_poster(item.poster_url)

        title.update(f"[bold]{item.title}[/bold]")
        year = str(item.year) if item.year else "—"
        source_color = _source_color(item.source_id)
        meta.update(f"[{color}]{label}[/{color}]  ·  {year}")
        pos = f"  [dim]{position}[/dim]" if position else ""
        badges.update(f"[{source_color}]⬢ {item.source_id}[/{source_color}]{pos}")
        genre_str = " · ".join(item.genres[:6])
        genres.update(f"[italic]{genre_str}[/italic]" if genre_str else "[dim]—[/dim]")
        overview.update(
            item.overview.strip() if item.overview else "[dim]No synopsis available.[/dim]"
        )
        verb = "▶ play episode" if item.kind in (MediaKind.SERIES, MediaKind.ANIME) else "▶ play"
        actions.update(f"[dim]Enter {verb} · d download · l save · i info[/dim]")
        source.update(f"[dim]ID: {item.id}[/dim]")

    @work(exclusive=True, thread=True)
    def _load_poster(self, url: str) -> None:
        path = download_image(url)
        if path is None:
            return

        def apply() -> None:
            if self._pending_poster_url != url:
                return  # user moved on to a different item while this downloaded
            try:
                poster = self.query_one("#detail-poster", PosterWidget)
            except Exception:  # noqa: BLE001 -- screen may have moved on
                return
            poster.show_image(path)

        self.app.call_from_thread(apply)

    def show_error_detail(self, message: str) -> None:
        self.query_one("#detail-overview", Static).update(f"[red]{message}[/red]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.run_search(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        # Genre funnel filters instantly as you type — no re-search.
        if event.input.id == "filter-genre":
            self._apply_filters_and_render()

    def on_select_changed(self, event: Select.Changed) -> None:
        # Every funnel control re-filters the fetched results instantly.
        if event.select.id in ("filter-kind", "filter-category", "filter-year", "filter-sort"):
            self._apply_filters_and_render()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "filter-clear":
            self.query_one("#filter-kind", Select).value = "All"
            self.query_one("#filter-category", Select).value = "All"
            self.query_one("#filter-genre", Input).value = ""
            self.query_one("#filter-year", Select).value = YEAR_OPTIONS[0]
            self.query_one("#filter-sort", Select).value = SORT_OPTIONS[0]
            self._apply_filters_and_render()
        elif event.button.id == "filter-toggle":
            self.action_toggle_filters()

    def action_toggle_filters(self) -> None:
        """Show/hide the ⩔ funnel bar."""
        bar = self.query_one("#filter-bar")
        bar.display = not bar.display
        if bar.display:
            self.query_one("#filter-genre", Input).focus()

    def _current_filters(self) -> dict:
        return {
            "kind": self.query_one("#filter-kind", Select).value,
            "category": self.query_one("#filter-category", Select).value,
            "genre": self.query_one("#filter-genre", Input).value or "",
            "year": self.query_one("#filter-year", Select).value,
            "sort": self.query_one("#filter-sort", Select).value,
        }

    def _update_filter_count(self, shown: int, total: int) -> None:
        self.query_one("#filter-count", Static).update(f"[dim]{shown}/{total}[/dim]")

    def _render_results(self, results: list[SearchResult]) -> None:
        list_view = self.query_one("#search-results", ListView)
        list_view.clear()
        for item in results:
            list_view.append(ResultItem(item))
        total = len(self._last_results)
        self._update_filter_count(len(results), total)
        if results:
            list_view.index = 0
            list_view.focus()
            self._show_detail(results[0], f"1 of {len(results)}")
        else:
            self._show_detail(None)

    def _apply_filters_and_render(self) -> None:
        """Apply the funnel to the last fetched results, instantly."""
        if not self._last_results:
            self._update_filter_count(0, 0)
            return
        self._render_results(apply_result_filters(self._last_results, **self._current_filters()))

    @work(exclusive=True)
    async def run_search(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        loading = self.query_one("#search-loading", LoadingIndicator)
        loading.display = True
        try:
            # Fan out to every enabled source, then funnel-filter
            # client-side so tweaking ⩔ never hits the network again.
            results: list[SearchResult] = []
            errors: list[str] = []
            for source in self.sources:
                try:
                    results.extend(await asyncio.to_thread(source.search, query))
                except SourceError as exc:
                    errors.append(f"{source.id}: {exc}")

            self._last_results = results
            self._render_results(apply_result_filters(results, **self._current_filters()))

            if errors:
                self.app.notify(" | ".join(errors), severity="error", timeout=8)
            elif not results:
                self.app.notify("No results found", severity="warning")
        finally:
            loading.display = False

    @work(exclusive=True)
    async def load_trending(self) -> None:
        """Fill the 🔥 Trending tab from every source with a feed."""
        if self._trending_loaded:
            return
        self._trending_loaded = True
        loading = self.query_one("#trending-loading", LoadingIndicator)
        loading.display = True
        try:
            results: list[SearchResult] = []
            for source in self.sources:
                try:
                    results.extend(await asyncio.to_thread(source.trending, 40))
                except SourceError:
                    continue
                if len(results) >= 60:
                    break
            list_view = self.query_one("#trending-results", ListView)
            list_view.clear()
            for item in results[:60]:
                list_view.append(ResultItem(item))
            if results:
                list_view.index = 0
            else:
                self.app.notify("No trending feed available", severity="warning")
        finally:
            loading.display = False

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        pane_id = getattr(event.pane, "id", None)
        if pane_id == "trending":
            self.load_trending()
        elif pane_id == "sources":
            self._populate_sources_list()

    def _find_source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id), None)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id not in ("search-results", "trending-results"):
            return
        item = event.item
        if isinstance(item, ResultItem):
            try:
                pos = event.list_view.children.index(item) + 1
                total = len(event.list_view.children)
                self._show_detail(item.item, f"{pos} of {total}")
            except ValueError:
                self._show_detail(item.item)
        else:
            self._show_detail(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ResultItem):
            self.open_item(item.item)
        elif isinstance(item, HistoryItem):
            self.resume_history_item(item)
        elif getattr(item, "source_id", None):
            self._toggle_source(item.source_id, not item.source_enabled)

    def _focused_result_item(self) -> SearchResult | None:
        """The highlighted title in whichever results list has focus
        (search, trending, or library)."""
        for list_id in ("#search-results", "#trending-results", "#library-results"):
            try:
                highlighted = self.query_one(list_id, ListView).highlighted_child
            except Exception:  # noqa: BLE001 -- tab may not be mounted yet
                continue
            if isinstance(highlighted, ResultItem):
                return highlighted.item
        return None

    def _toggle_source(self, source_id: str, enable: bool) -> None:
        """Enable or disable a source (persisted to config.toml)."""
        if enable:
            if source_id not in self.config.enabled_sources:
                self.config.enabled_sources.append(source_id)
                self.app.notify(f"Enabled source: {source_id}")
        else:
            if source_id in self.config.enabled_sources:
                self.config.enabled_sources.remove(source_id)
                self.app.notify(f"Disabled source: {source_id}")
        try:
            from torrentio_tui.config import save_enabled_sources

            save_enabled_sources(self.config.enabled_sources)
        except Exception:
            pass
        self._reload_sources()

    def action_toggle_library(self) -> None:
        item = self._focused_result_item()
        if item is None:
            self.app.notify("Highlight a title first", severity="warning")
            return
        if self.library.contains(item):
            self.library.remove(item)
            self.app.notify(f"Removed from library: {item.title}")
        else:
            self.library.add(item)
            self.app.notify(f"Saved to library: {item.title}")
        self.refresh_library()

    def action_info(self) -> None:
        item = self._focused_result_item()
        if item is None:
            return
        genres = ", ".join(item.genres) if item.genres else "—"
        self.app.notify(
            f"{item.title} ({item.year or '—'})\n"
            f"Kind: {item.kind.value}  ·  Genres: {genres}\n"
            f"Source: {item.source_id}  ·  ID: {item.id}",
            title="Info",
            timeout=8,
        )

    def action_focus_search(self) -> None:
        self.query_one(TabbedContent).active = "search"
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
        search_input.select_all()

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_sources(self) -> None:
        """Show the sources management tab."""
        self.query_one(TabbedContent).active = "sources"
        self._populate_sources_list()

    def _populate_sources_list(self) -> None:
        """Populate the sources list view with all available sources,
        including disabled ones so they can be re-enabled. Adult sources
        stay hidden unless unlocked in Settings (g) — default off."""
        from torrentio_tui.sources.registry import (
            _AVAILABLE,
            CATEGORIES,
            describe_source,
        )

        list_view = self.query_one("#sources-list", ListView)
        list_view.clear()

        # Group ALL registered sources by category (not just enabled),
        # so disabled ids remain visible and toggleable.
        sources_by_cat: dict[str, list[str]] = {}
        for source_id, cls in _AVAILABLE.items():
            cat = getattr(cls, "category", "streams")
            sources_by_cat.setdefault(cat, []).append(source_id)

        adult_unlocked = bool(self.config.adult.enabled)

        # Add category headers and sources
        for cat_id, (cat_label, cat_desc) in CATEGORIES.items():
            cat_sources = sorted(sources_by_cat.get(cat_id, []))
            if cat_id == "adult" and not adult_unlocked:
                hint = ListItem(
                    Static(
                        "[bold]🔞 Adult (opt-in)[/bold]  "
                        "[dim]hidden — press g for Settings to unlock[/dim]",
                        markup=True,
                    ),
                    disabled=True,
                    classes="category-header",
                )
                list_view.append(hint)
                continue
            if not cat_sources:
                continue

            # Category header with live enabled/total counts
            enabled_count = sum(1 for sid in cat_sources if sid in self.config.enabled_sources)
            header = ListItem(
                Static(
                    f"[bold]{cat_label}[/bold]  [dim]{cat_desc}[/dim]  "
                    f"[dim]({enabled_count}/{len(cat_sources)} on)[/dim]",
                    markup=True,
                ),
                disabled=True,
                classes="category-header",
            )
            list_view.append(header)

            # Sources in this category
            for source_id in cat_sources:
                enabled = source_id in self.config.enabled_sources
                status = "[green]✓ Enabled[/green]" if enabled else "[red]✗ Disabled[/red]"
                label = f"  {describe_source(source_id)}  [dim]({source_id})[/dim]  {status}"
                item = ListItem(Static(label, markup=True))
                item.source_id = source_id
                item.source_enabled = enabled
                list_view.append(item)
        if len(list_view.children) > 0:
            list_view.index = 0

    def action_cycle_theme(self) -> None:
        from torrentio_tui.config import THEMES, save_theme
        from torrentio_tui.themes import load_custom_themes

        # Re-scan the themes directory so a file added/edited since the app
        # started shows up in the cycle without needing a restart.
        self.app.sync_custom_themes()
        custom_names = sorted(t.name for t in load_custom_themes() if t.name not in THEMES)
        cycle = (*THEMES, *custom_names)

        current = self.app.theme
        try:
            next_theme = cycle[(cycle.index(current) + 1) % len(cycle)]
        except ValueError:
            next_theme = cycle[0]
        self.app.theme = next_theme
        self.config.ui.theme = next_theme
        save_theme(next_theme)
        self.app.notify(f"Theme: {next_theme}", timeout=3)

    def action_download(self) -> None:
        item = self._focused_result_item()
        if item is None:
            self.app.notify("Highlight a title first", severity="warning")
            return
        self._download_item(item)

    def action_settings(self) -> None:
        """Open Settings (adult toggle, theme, player, ...)."""
        from torrentio_tui.ui.screens.settings import SettingsScreen

        self.app.push_screen(SettingsScreen(self.config), self._on_settings_closed)

    def _on_settings_closed(self, changed: object) -> None:
        """Reload sources/views after Settings dismisses.

        `changed` is True when anything that affects loaded sources
        (adult toggle) was flipped.
        """
        if changed:
            self._reload_sources()
            self._trending_loaded = False
        self.refresh_continue_watching()
        self.refresh_library()

    def _reload_sources(self) -> None:
        """Rebuild `self.sources` from config + refresh the Sources tab."""
        from torrentio_tui.sources.registry import load_sources

        try:
            self.sources = load_sources(self.config)
        except Exception as exc:  # noqa: BLE001 -- config gates raise SourceError
            self.app.notify(f"Failed to reload sources: {exc}", severity="error")
        self._populate_sources_list()

    @work(exclusive=True)
    async def _download_item(self, item: SearchResult) -> None:
        try:
            await self._download_item_inner(item)
        except Exception as exc:  # noqa: BLE001 -- must never fail silently
            message = f"Download failed ({type(exc).__name__}): {exc}"
            self.app.notify(message, severity="error", timeout=10)

    async def _download_item_inner(self, item: SearchResult) -> None:
        source = self._find_source(item.source_id)
        if source is None:
            self.app.notify(
                f"No loaded source matches '{item.source_id}' — is it still enabled?",
                severity="error",
                timeout=10,
            )
            return

        episode: Episode
        if item.kind in (MediaKind.SERIES, MediaKind.ANIME):
            episodes = await asyncio.to_thread(source.get_episodes, item)
            picked = await self.app.push_screen_wait(EpisodeScreen(episodes, title=item.title))
            if picked is None:
                return
            episode = picked
        else:
            episode = Episode(id=item.id, title=item.title)

        try:
            streams = await asyncio.to_thread(source.get_streams, item, episode)
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

    def _set_download_status(self, text: str | None) -> None:
        status = self.query_one("#download-status", Static)
        status.display = text is not None
        if text is not None:
            status.update(text)

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
        self.app.call_from_thread(self._set_download_status, f"⏳ Starting: {title}")

        def on_output(line: str) -> None:
            status_text = _format_download_progress(title, line)
            if status_text:
                self.app.call_from_thread(self._set_download_status, status_text)

        try:
            dest = download(
                stream, title, Path(self.config.downloads.directory), on_output=on_output
            )
        except DownloadError as exc:
            self.app.call_from_thread(self._set_download_status, None)
            self.app.call_from_thread(self.app.notify, str(exc), severity="error", timeout=10)
            return
        self.app.call_from_thread(self._set_download_status, None)
        self.app.call_from_thread(
            self.app.notify, f"Saved to {dest}", severity="information", timeout=8
        )

    @work(exclusive=True)
    async def open_item(self, item: SearchResult) -> None:
        try:
            await self._open_item(item)
        except Exception as exc:  # noqa: BLE001 -- last resort so a click never just does nothing
            message = f"Couldn't open '{item.title}' ({type(exc).__name__}): {exc}"
            self.app.notify(message, severity="error", timeout=10)
            self.show_error_detail(message)

    async def _open_item(self, item: SearchResult) -> None:
        source = self._find_source(item.source_id)
        if source is None:
            message = f"No loaded source matches '{item.source_id}' — is it still enabled?"
            self.app.notify(message, severity="error", timeout=10)
            self.show_error_detail(message)
            return

        episode: Episode
        if item.kind in (MediaKind.SERIES, MediaKind.ANIME):
            episodes = await asyncio.to_thread(source.get_episodes, item)
            picked = await self.app.push_screen_wait(EpisodeScreen(episodes, title=item.title))
            if picked is None:
                return
            episode = picked
        else:
            episode = Episode(id=item.id, title=item.title)

        try:
            streams = await asyncio.to_thread(source.get_streams, item, episode)
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

        await self.play_stream(item, episode, stream)

    @work(exclusive=True)
    async def resume_history_item(self, hist_item: HistoryItem) -> None:
        source = self._find_source(hist_item.source_id)
        if source is None:
            return
        entry = self.history.get(hist_item.source_id, hist_item.item_id)
        if entry is None:
            return
        # History doesn't store MediaKind; an episode label means this was
        # a series/anime episode, so resume as SERIES to keep
        # get_episodes/get_streams routing working.
        kind = MediaKind.SERIES if entry.episode_label else MediaKind.MOVIE
        result = SearchResult(
            id=hist_item.item_id,
            title=entry.title,
            kind=kind,
            source_id=hist_item.source_id,
        )
        episode = Episode(
            id=hist_item.item_id,
            title=entry.episode_label or entry.title,
        )
        try:
            streams = await asyncio.to_thread(source.get_streams, result, episode)
        except SourceError as exc:
            self.app.notify(str(exc), severity="error", timeout=10)
            return
        if streams:
            await self.play_stream(
                result, episode, streams[0], resume_seconds=entry.position_seconds
            )

    async def play_stream(
        self, item: SearchResult, episode: Episode, stream, resume_seconds: float = 0.0
    ) -> None:
        from torrentio_tui.player.torrent import is_torrent_link
        from torrentio_tui.sources.subtitles import attach_subtitles

        # Auto-subtitles (opt-in via [subtitles]): runs off the event loop,
        # never raises, returns the stream unchanged when disabled.
        stream = await asyncio.to_thread(attach_subtitles, stream, item, episode, self.config)
        use_hud = (
            self.config.player.backend == "mpv"
            and self.config.player.hud
            and not is_torrent_link(stream.url)
        )
        error = (
            await self._play_with_hud(stream, item.title, resume_seconds)
            if use_hud
            else self._play_blocking(stream, item, resume_seconds)
        )

        if error is not None:
            message = _format_playback_error(error, self.config.player.backend)
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

    def _play_blocking(self, stream, item: SearchResult, resume_seconds: float) -> Exception | None:
        from textual.app import SuspendNotSupported

        player = get_player(
            self.config.player.backend, hwdec=self.config.player.hwdec
        )  # Textual's App.suspend() only resumes/refreshes the terminal driver
        # if the code inside the `with` block returns *normally* — it has no
        # try/finally around its internal yield. Any exception raised by
        # player.play() (TorrentStreamError, a missing player binary, or
        # anything else — a bug here should never be able to take the whole
        # app down silently) would otherwise propagate straight through the
        # `with` block and skip resume_application_mode()/refresh() entirely,
        # leaving the terminal stuck in suspended raw mode — blank screen,
        # no redraw, effectively dead. So player.play() is wrapped *inside*
        # the `with` block and every exception it could raise is caught
        # there, letting suspend() complete its normal resume path first.
        #
        # suspend() itself can also raise SuspendNotSupported — from its own
        # __enter__, before anything is actually suspended (some terminal
        # drivers don't support it) — which is safe to catch around the
        # whole `with` since no raw-mode switch ever happened in that case.
        error: Exception | None = None
        try:
            with self.app.suspend():
                try:
                    returncode = player.play(
                        stream, title=item.title, resume_seconds=resume_seconds
                    )
                except Exception as exc:  # noqa: BLE001 -- must never escape suspend()
                    error = exc
                else:
                    if returncode != 0:
                        # A crashed streamer / player exit must surface as
                        # an error, not get recorded as "watched".
                        error = RuntimeError(
                            f"Player '{self.config.player.backend}' exited with code {returncode}"
                        )
        except SuspendNotSupported as exc:
            error = exc
        return error

    async def _play_with_hud(self, stream, title: str, resume_seconds: float) -> Exception | None:
        from torrentio_tui.ui.screens.playback_hud import PlaybackHudScreen

        screen = PlaybackHudScreen(stream, title, self.config.player.hwdec, resume_seconds)
        await self.app.push_screen_wait(screen)
        if screen.spawn_error is not None:
            return screen.spawn_error
        if not screen.user_stopped and screen.exit_code not in (None, 0):
            return RuntimeError(f"mpv exited with code {screen.exit_code}")
        return None
