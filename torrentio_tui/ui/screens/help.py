from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from torrentio_tui.config import THEMES

KEYBINDINGS = (
    ("↑ / ↓", "Move selection in lists"),
    ("← / →", "Switch tabs (Search / Continue / Library)"),
    ("Enter", "Play selected title / episode / stream"),
    ("Tab", "Switch focus between search box, results, detail panel"),
    ("l", "Save/unsave highlighted title in your Library (❤️)"),
    ("d", "Download highlighted title (requires yt-dlp)"),
    ("i", "Show detailed info for highlighted title"),
    ("t", f"Cycle theme ({', '.join(THEMES)})"),
    ("?", "Show this help screen"),
    ("Esc", "Close picker / help screen / go back"),
    ("q", "Quit application"),
)

SOURCES_INFO = (
    ("stremio", "Cinemeta + Torrentio (movies, series, anime)"),
    ("mediafusion", "MediaFusion addon (debrid-friendly streams)"),
    ("knightcrawler", "Knightcrawler addon (alt streams)"),
    ("torrentio-selfhost", "Self-hosted Torrentio instance"),
    ("iptv", "Live TV channels from M3U playlist"),
    ("anilist", "Anime metadata from AniList (GraphQL)"),
    ("nyaa", "Anime torrents from Nyaa.si"),
    ("subsplease", "Latest anime releases from SubsPlease"),
    ("local", "Local video files (~/Videos by default)"),
    ("stremio-adult", "Adult content via Stremio (opt-in)"),
    ("hanime", "Hentai anime from Hanime.tv (opt-in)"),
)

TIPS = (
    "Enable multiple sources in config.toml [sources].enabled for wider results.",
    "Torrentio may return magnet links — install webtorrent-cli or peerflix, or add a debrid key.",
    "If Torrentio is blocked (HTTP 403), set network.proxy_url (e.g., Cloudflare WARP).",
    "MediaFusion often works without proxy and returns direct debrid links.",
    "Configure IPTV: add m3u_url or m3u_path under [sources.iptv].",
    "Adult content (stremio-adult, hanime) requires [adult] enabled = true in config.",
    "Use --doctor to check connectivity and installed tools.",
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
            source_lines = "\n".join(
                f"[bold cyan]{src:<18}[/bold cyan]  {desc}" for src, desc in SOURCES_INFO
            )
            yield Static(source_lines, classes="help-body", markup=True)

            yield Static("\n💡  Tips", classes="help-title", markup=True)
            tip_lines = "\n".join(f"  • {tip}" for tip in TIPS)
            yield Static(tip_lines, classes="help-body", markup=True)
        yield Footer()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
