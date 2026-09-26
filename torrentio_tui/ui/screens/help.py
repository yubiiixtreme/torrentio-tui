from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

KEYBINDINGS = (
    ("↑ / ↓", "Move selection in lists"),
    ("← / →", "Switch tabs (Search / Continue / Library)"),
    ("Enter", "Play selected title / episode / stream"),
    ("Tab", "Switch focus between search box, results, detail panel"),
    ("l", "Save/unsave highlighted title in your Library (❤️)"),
    ("d", "Download highlighted title (requires yt-dlp)"),
    ("i", "Show detailed info for highlighted title"),
    ("?", "Show this help screen"),
    ("Esc", "Close picker / help screen / go back"),
    ("q", "Quit application"),
)

SOURCES_INFO = (
    # Main streaming sources
    ("stremio", "Cinemeta + Torrentio (movies, series, anime)"),
    ("mediafusion", "MediaFusion addon — debrid-friendly, no proxy needed"),
    ("knightcrawler", "Knightcrawler addon (alt streams)"),
    ("torrentio-selfhost", "Self-hosted Torrentio instance"),
    ("debridmediamanager", "Debrid Media Manager (debridmediamanager.com)"),
    ("torrentio-mirror1", "Torrentio mirror (Cloudflare)"),
    ("torrentio-mirror2", "Torrentio mirror (Vercel)"),
    ("torrentio-mirror3", "Torrentio mirror (Kavin)"),
    ("comet", "Comet addon (comet.strem.io)"),
    # Local indexers (need local instance)
    ("jackett", "Jackett indexer (localhost:9117)"),
    ("prowlarr", "Prowlarr indexer (localhost:9696)"),
    ("radarr", "Radarr movie manager (localhost:7878)"),
    ("sonarr", "Sonarr series manager (localhost:8989)"),
    ("overseerr", "Overseerr request manager (localhost:5055)"),
    # Media servers
    ("jellyfin", "Jellyfin media server (localhost:8096)"),
    ("plex", "Plex media server (localhost:32400)"),
    ("emby", "Emby media server (localhost:8096)"),
    # IPTV / Live TV
    ("iptv", "Live TV channels from M3U playlist (URL or file)"),
    # Anime-specific sources
    ("anilist", "Anime metadata from AniList (GraphQL)"),
    ("nyaa", "Anime torrents from Nyaa.si"),
    ("subsplease", "Latest anime releases from SubsPlease"),
    ("kitsu", "Kitsu anime metadata"),
    ("animeflv", "AnimeFLV torrents"),
    ("crunchyroll", "Crunchyroll metadata"),
    # Adult content (opt-in)
    ("stremio-adult", "Adult content via Stremio (opt-in)"),
    ("hanime", "Hentai anime from Hanime.tv (opt-in)"),
    ("nhentai", "NHentai (opt-in)"),
    ("e-hentai", "E-Hentai (opt-in)"),
    # Generic
    ("stremio-addon", "Generic Stremio addon (configure stream_url)"),
    ("local", "Local video files (~/Videos by default)"),
)

TIPS = (
    "Enable multiple sources in config.toml [sources].enabled for wider results.",
    "Torrentio may return magnet links — install peerflix (preferred) or webtorrent-cli, or add a debrid key.",
    "If Torrentio is blocked (HTTP 403), set network.proxy_url (e.g., Cloudflare WARP).",
    "MediaFusion often works without proxy and returns direct debrid links (configure at mediafusion.elfhosted.com/configure).",
    "Local indexers (Jackett, Prowlarr, Radarr, Sonarr) need running instances on your network.",
    "Media servers (Jellyfin, Plex, Emby) need local instances with Stremio addon configured.",
    "Configure IPTV: add m3u_url or m3u_path under [sources.iptv].",
    "Adult content requires [adult] enabled = true in config (legal age only).",
    "Anime sources: AniList for metadata, Nyaa/SubsPlease for torrents/releases.",
    "Use --doctor to check connectivity and installed tools.",
    "Press 'i' on any result for detailed info including genres and source.",
    "Press 'l' to save/unsave to your library (❤️ tab).",
    "Press 'd' to download via yt-dlp (needs direct http links or debrid).",
)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss_help", "Close"), ("question_mark", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="help-container"):
            yield Static("⌨  Keybindings", id="help-title")
            lines = "\n".join(f"[bold]{key:<10}[/bold]  {desc}" for key, desc in KEYBINDINGS)
            yield Static(lines, id="help-body", markup=True)

            yield Static("\n📡  Available Sources", id="help-title", markup=True)
            source_lines = "\n".join(
                f"[bold cyan]{src:<18}[/bold cyan]  {desc}" for src, desc in SOURCES_INFO
            )
            yield Static(source_lines, id="help-body", markup=True)

            yield Static("\n💡  Tips", id="help-title", markup=True)
            tip_lines = "\n".join(f"  • {tip}" for tip in TIPS)
            yield Static(tip_lines, id="help-body", markup=True)
        yield Footer()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
