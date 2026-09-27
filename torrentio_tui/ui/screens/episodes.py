from __future__ import annotations

from itertools import groupby

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from torrentio_tui.models import Episode
from torrentio_tui.ui.widgets import VimListView


class EpisodePicked(ListItem):
    def __init__(self, episode: Episode) -> None:
        if episode.season is not None and episode.number is not None:
            label = f"[bold cyan]S{episode.season:02d}E{episode.number:02d}[/bold cyan]  [white]{episode.title}[/white]"
        else:
            label = f"[white]{episode.title}[/white]"
        super().__init__(Static(label, markup=True))
        self.episode = episode


class SeasonHeader(ListItem):
    """A non-selectable separator row -- ListView's cursor navigation
    (arrows and j/k alike, since they share the same action) already
    skips `disabled` items on its own, so this just needs to render."""

    def __init__(self, season: int | None) -> None:
        label = f"── Season {season} ──" if season is not None else "── Episodes ──"
        super().__init__(Static(f"[dim bold]{label}[/dim bold]", markup=True), disabled=True)


def _build_episode_rows(episodes: list[Episode]) -> list[ListItem]:
    """One `SeasonHeader` per season boundary followed by its episodes.
    Episodes already arrive season-then-number sorted from the source,
    so this only needs to notice when `season` changes -- no re-sorting."""
    rows: list[ListItem] = []
    multiple_seasons = len({ep.season for ep in episodes}) > 1
    for season, group in groupby(episodes, key=lambda ep: ep.season):
        if multiple_seasons:
            rows.append(SeasonHeader(season))
        rows.extend(EpisodePicked(ep) for ep in group)
    return rows


class EpisodeScreen(ModalScreen[Episode | None]):
    """Pick an episode. Dismisses with the chosen Episode, or None on cancel."""

    BINDINGS = [("escape", "cancel", "Back")]

    def __init__(self, episodes: list[Episode]) -> None:
        super().__init__()
        self.episodes = episodes

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="episode-list-container"):
            yield Static("📺  Choose Episode", id="episode-title")
            yield VimListView(*_build_episode_rows(self.episodes))
        yield Footer()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        if self.episodes:
            list_view.index = 0
            if isinstance(list_view.highlighted_child, SeasonHeader):
                list_view.action_cursor_down()
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, EpisodePicked):
            self.dismiss(item.episode)

    def action_cancel(self) -> None:
        self.dismiss(None)
