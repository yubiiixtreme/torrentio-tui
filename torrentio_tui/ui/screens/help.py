from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from torrentio_tui.config import THEMES
from torrentio_tui.sources.registry import CATEGORIES, describe_source, sources_by_category

KEYBINDINGS = (
    ("↑ / ↓ or k / j", "Move selection in lists"),
    ("← / →", "Switch tabs (Search / Continue / Library)"),
    ("Enter", "Play selected title / episode / stream"),
    ("Tab", "Switch focus between search box, results, detail panel"),
    ("/", "Jump to search box and select its contents"),
    ("l", "Save/unsave highlighted title in your Library (❤️)"),
    ("d", "Download highlighted title (requires yt-dlp)"),
    ("i", "Show detailed info for highlighted title"),
    ("t", f"Cycle theme ({', '.join(THEMES)})"),
    ("s", "Open the Sources tab to enable/disable providers"),
    ("?", "Show this help screen"),
    ("Esc", "Close picker / help screen / go back"),
    ("q", "Quit application"),
)


def _source_lines() -> str:
    """Source list grouped by category, generated from the registry so it
    never goes stale when sources are added or removed."""
    blocks = []
    for category_id, entries in sources_by_category().items():
        label = CATEGORIES.get(category_id, (category_id, ""))[0]
        blocks.append(f"[bold]{label}[/bold]")
        for source_id, _cls in entries:
            blocks.append(f"  [bold cyan]{source_id:<18}[/bold cyan]  {describe_source(source_id)}")
    return "\n".join(blocks)


TIPS = (
    "Enable multiple sources in config.toml [sources].enabled for wider results.",
    "Torrentio may return magnet links — install webtorrent-cli or peerflix, or add a debrid key.",
    "If Torrentio is blocked (HTTP 403), set network.proxy_url (e.g., Cloudflare WARP).",
    "MediaFusion often works without proxy and returns direct debrid links.",
    "Configure IPTV: add m3u_url or m3u_path under [sources.iptv].",
    "Adult content (stremio-adult, hanime, nhentai, rule34) requires [adult] enabled = true in config.",
    "Catalogue sources (tvmaze, jikan, kitsu, anilist) resolve playback through your stream addon.",
    "Set [subtitles] enabled = true to auto-attach SubDB/OpenSubtitles captions at playback.",
    "Use --doctor to check connectivity and installed tools.",
    "Any theme you pick (t or Ctrl+P) is saved and restored next launch.",
    "Set [player] hud = true for a live buffer/speed HUD instead of a full-"
    "screen mpv (needs mpv's own GUI window -- not for headless/SSH setups).",
)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss_help", "Close"), ("question_mark", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="help-container"), VerticalScroll():
            yield Static("⌨  Keybindings", classes="help-title")
            lines = "\n".join(f"[bold]{key:<10}[/bold]  {desc}" for key, desc in KEYBINDINGS)
            yield Static(lines, classes="help-body", markup=True)

            yield Static("\n📡  Available Sources", classes="help-title", markup=True)
            yield Static(_source_lines(), classes="help-body", markup=True)

            yield Static("\n💡  Tips", classes="help-title", markup=True)
            tip_lines = "\n".join(f"  • {tip}" for tip in TIPS)
            yield Static(tip_lines, classes="help-body", markup=True)
        yield Footer()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
