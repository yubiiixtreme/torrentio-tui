from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from torrentio_tui.config import (
    THEMES,
    Config,
    save_adult_enabled,
    save_download_dir,
    save_enabled_sources,
    save_player_backend,
    save_subtitles_enabled,
    save_theme,
)
from torrentio_tui.ui.widgets import VimListView


class SettingRow(ListItem):
    """One toggleable settings row."""

    def __init__(self, action: str, label: str) -> None:
        super().__init__(Static(label, markup=True))
        self.setting_action = action


def _on_off(value: bool) -> str:
    return "[green]ON[/green]" if value else "[red]OFF[/red]"


class SettingsScreen(ModalScreen[bool]):
    """App settings. Dismisses True when the adult toggle changed (so the
    main screen knows to reload sources), False otherwise.

    Adult content stays OFF by default; the theme (and every other choice
    here) is written to config.toml immediately, so it persists to the
    next launch.
    """

    BINDINGS = [("escape", "close", "Back")]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._sources_changed = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="settings-container"):
            yield Static(
                "⚙  Settings  [dim](Enter toggles, Esc saves & closes)[/dim]", id="settings-title"
            )
            yield VimListView(id="settings-list")
            yield Input(
                str(self.config.downloads.directory),
                placeholder="~/Videos/torrentio-tui",
                id="settings-downloaddir",
            )
            yield Static(
                "[dim]⬇ download folder — type a path, press Enter to save[/dim]",
                id="settings-download-hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_rows()
        self.query_one(ListView).focus()

    # -- rows -----------------------------------------------------------
    def _rows(self) -> list[tuple[str, str]]:
        adult = _on_off(self.config.adult.enabled)
        subs = _on_off(self.config.subtitles.enabled)
        return [
            ("adult", f"🔞  Adult content  {adult}  [dim](default off)[/dim]"),
            ("theme", f"🎨  Theme  [bold]{self.app.theme}[/bold]  [dim](t also cycles)[/dim]"),
            ("player", f"▶  Player  [bold]{self.config.player.backend}[/bold]"),
            ("subtitles", f"💬  Auto-subtitles  {subs}"),
        ]

    def _refresh_rows(self) -> None:
        list_view = self.query_one("#settings-list", ListView)
        list_view.clear()
        for action, label in self._rows():
            list_view.append(SettingRow(action, label))
        list_view.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, SettingRow):
            return
        if item.setting_action == "adult":
            self._toggle_adult()
        elif item.setting_action == "theme":
            self._cycle_theme()
        elif item.setting_action == "player":
            self._cycle_player()
        elif item.setting_action == "subtitles":
            self._toggle_subtitles()
        self._refresh_rows()
        self.query_one(ListView).focus()

    # -- toggles ---------------------------------------------------------
    def _toggle_adult(self) -> None:
        enabled = not self.config.adult.enabled
        self.config.adult.enabled = enabled
        save_adult_enabled(enabled)
        if not enabled:
            # Locking adult content also unloads any adult sources so
            # nothing adult can be searched or played afterwards.
            from torrentio_tui.sources.registry import _AVAILABLE

            adult_ids = {
                sid for sid, cls in _AVAILABLE.items() if getattr(cls, "category", "") == "adult"
            }
            remaining = [s for s in self.config.enabled_sources if s not in adult_ids]
            if remaining != self.config.enabled_sources:
                self.config.enabled_sources = remaining
                save_enabled_sources(remaining)
        self._sources_changed = True
        if enabled:
            self.app.notify("Adult unlocked 🔓 — enable sources in the Sources tab", timeout=5)
        else:
            self.app.notify("Adult content locked 🔒", timeout=4)

    def _cycle_theme(self) -> None:
        from torrentio_tui.themes import load_custom_themes

        self.app.sync_custom_themes()
        custom_names = sorted(t.name for t in load_custom_themes() if t.name not in THEMES)
        cycle = (*THEMES, *custom_names)
        try:
            next_theme = cycle[(cycle.index(self.app.theme) + 1) % len(cycle)]
        except ValueError:
            next_theme = cycle[0]
        self.app.theme = next_theme
        self.config.ui.theme = next_theme
        save_theme(next_theme)
        self.app.notify(f"Theme: {next_theme}", timeout=3)

    def _cycle_player(self) -> None:
        from torrentio_tui.player.registry import available_player_ids

        ids = available_player_ids()
        try:
            nxt = ids[(ids.index(self.config.player.backend) + 1) % len(ids)]
        except ValueError:
            nxt = ids[0]
        self.config.player.backend = nxt
        save_player_backend(nxt)
        self.app.notify(f"Player: {nxt}", timeout=3)

    def _toggle_subtitles(self) -> None:
        enabled = not self.config.subtitles.enabled
        self.config.subtitles.enabled = enabled
        save_subtitles_enabled(enabled)
        self.app.notify(f"Auto-subtitles {_on_off(enabled)}", timeout=3)

    # -- download dir ----------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "settings-downloaddir":
            from pathlib import Path

            value = event.value.strip() or str(self.config.downloads.directory)
            self.config.downloads.directory = Path(value).expanduser()
            save_download_dir(value)
            self.app.notify(f"Download folder: {value}", timeout=4)
            self.query_one(ListView).focus()

    def action_close(self) -> None:
        self.dismiss(self._sources_changed)
