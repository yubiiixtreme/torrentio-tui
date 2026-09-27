"""Live playback HUD: elapsed/duration, buffer health, and a cache-speed
sparkline. Pure rendering -- whoever polls mpv's IPC calls `update_stats`;
this widget has no idea where the numbers come from.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ProgressBar, Sparkline, Static

#: Seconds of read-ahead treated as a "full" buffer bar. mpv's default
#: demuxer cache is much larger, but past ~10s of read-ahead there's no
#: practical stall risk left to communicate to the user.
_BUFFER_FULL_SECONDS = 10.0

#: Cache-speed samples kept for the sparkline -- recent trend, not history.
_MAX_SPEED_SAMPLES = 60


class StreamHud(Vertical):
    DEFAULT_CSS = """
    StreamHud {
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    StreamHud #hud-title { text-style: bold; color: $primary; height: 1; }
    StreamHud .hud-row { height: 1; margin-top: 1; }
    StreamHud .hud-row Static { width: auto; padding: 0 1 0 0; }
    StreamHud .hud-row ProgressBar { width: 1fr; }
    StreamHud #hud-speed-section { height: 5; margin-top: 1; }
    StreamHud #hud-speed-sparkline { height: 3; }
    """

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._speed_samples: list[float] = []

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="hud-title")
        with Horizontal(classes="hud-row"):
            yield Static("⏵", id="hud-play-state")
            yield ProgressBar(id="hud-elapsed", show_eta=False)
            yield Static("--:-- / --:--", id="hud-time")
        with Horizontal(classes="hud-row"):
            yield Static("Buffer", id="hud-buffer-label")
            yield ProgressBar(id="hud-buffer", show_eta=False, total=100)
        with Vertical(id="hud-speed-section"):
            yield Static("Cache speed (KB/s)", id="hud-speed-label")
            yield Sparkline([], summary_function=max, id="hud-speed-sparkline")

    def update_stats(
        self,
        *,
        paused: bool,
        position_seconds: float,
        duration_seconds: float | None,
        buffered_seconds: float,
        cache_speed_bytes: float,
    ) -> None:
        self.query_one("#hud-play-state", Static).update("⏸" if paused else "⏵")

        elapsed = self.query_one("#hud-elapsed", ProgressBar)
        if duration_seconds:
            elapsed.total = duration_seconds
            elapsed.progress = min(position_seconds, duration_seconds)
        else:
            elapsed.total = None  # unknown duration (e.g. a live stream) -- indeterminate bar
        self.query_one("#hud-time", Static).update(
            f"{_format_time(position_seconds)} / {_format_time(duration_seconds)}"
        )

        buffer_pct = min(max(buffered_seconds, 0.0) / _BUFFER_FULL_SECONDS, 1.0) * 100
        self.query_one("#hud-buffer", ProgressBar).progress = buffer_pct

        self._speed_samples.append(cache_speed_bytes / 1024)
        del self._speed_samples[:-_MAX_SPEED_SAMPLES]
        self.query_one("#hud-speed-sparkline", Sparkline).data = list(self._speed_samples)


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"
