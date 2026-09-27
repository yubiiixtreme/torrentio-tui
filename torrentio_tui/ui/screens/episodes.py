from __future__ import annotations

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
            yield VimListView(*[EpisodePicked(ep) for ep in self.episodes])
        yield Footer()

    def on_mount(self) -> None:
        list_view = self.query_one(ListView)
        if self.episodes:
            list_view.index = 0
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, EpisodePicked):
            self.dismiss(item.episode)

    def action_cancel(self) -> None:
        self.dismiss(None)
