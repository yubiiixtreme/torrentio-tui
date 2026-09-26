from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from stream_tui.models import Episode


class EpisodePicked(ListItem):
    def __init__(self, episode: Episode) -> None:
        label = episode.title
        if episode.season is not None and episode.number is not None:
            label = f"S{episode.season:02d}E{episode.number:02d} - {episode.title}"
        super().__init__(Static(label))
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
            yield ListView(*[EpisodePicked(ep) for ep in self.episodes])
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, EpisodePicked):
            self.dismiss(item.episode)

    def action_cancel(self) -> None:
        self.dismiss(None)
