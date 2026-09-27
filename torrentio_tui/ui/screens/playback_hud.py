"""Backgrounded mpv playback with a live in-app HUD.

Unlike the default backend, which suspends the whole TUI and hands mpv
the terminal, this runs mpv with its own GUI window (`--no-terminal`)
and drives it over its JSON IPC socket -- so the app stays visible and
can show buffer health / cache speed instead of going dark until mpv
exits. Only used when `[player] hud = true` is set and the stream isn't
a magnet/torrent link (peerflix/webtorrent don't expose an equivalent
IPC to poll).
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer

from torrentio_tui.models import StreamLink
from torrentio_tui.player.mpv_ipc import MpvIPC, MpvIPCError
from torrentio_tui.player.process import (
    ensure_signal_handlers_installed,
    register_process,
    terminate_group,
    unregister_process,
)
from torrentio_tui.ui.widgets.hud import StreamHud

_POLL_INTERVAL_SECONDS = 0.5


class PlaybackHudScreen(ModalScreen[None]):
    BINDINGS = [
        ("space", "toggle_pause", "Pause/Resume"),
        ("left", "seek_back", "-10s"),
        ("right", "seek_forward", "+10s"),
        ("q", "stop", "Stop"),
        ("escape", "stop", "Stop"),
    ]

    DEFAULT_CSS = """
    PlaybackHudScreen {
        align: center middle;
    }
    PlaybackHudScreen > Vertical {
        width: 70%;
        height: auto;
    }
    """

    def __init__(
        self, stream: StreamLink, title: str, hwdec: str, resume_seconds: float = 0.0
    ) -> None:
        super().__init__()
        self._stream = stream
        self._title = title
        self._hwdec = hwdec
        self._resume_seconds = resume_seconds
        self._tmpdir = tempfile.mkdtemp(prefix="torrentio-tui-mpv-")
        self._socket_path = Path(self._tmpdir) / "mpv.sock"
        self._process: subprocess.Popen | None = None
        self._ipc: MpvIPC | None = None
        self._stopped = False
        #: Set if mpv couldn't even be spawned (missing binary, etc.) --
        #: read back by the caller after this screen is dismissed.
        self.spawn_error: Exception | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield StreamHud(self._title, id="stream-hud")
        yield Footer()

    def on_mount(self) -> None:
        cmd = self._build_command()
        ensure_signal_handlers_installed()  # Screen lifecycle runs on the main thread; safe here.
        try:
            self._process = subprocess.Popen(cmd, start_new_session=True)
        except OSError as exc:
            self.spawn_error = exc
            self.dismiss()
            return

        register_process(self._process)
        self._ipc = MpvIPC(self._socket_path, is_alive=self._process_alive)
        try:
            self._ipc.connect(timeout=5.0)
        except MpvIPCError:
            # mpv is still running video -- just no live numbers for the HUD.
            self._ipc = None

        self.set_interval(_POLL_INTERVAL_SECONDS, self._poll)
        self._watch_process()

    def _build_command(self) -> list[str]:
        cmd = [
            "mpv",
            f"--force-media-title={self._title}",
            "--save-position-on-quit",
            "--no-terminal",
            f"--input-ipc-server={self._socket_path}",
        ]
        if self._hwdec:
            cmd.append(f"--hwdec={self._hwdec}")
        if self._resume_seconds > 0:
            cmd.append(f"--start={self._resume_seconds}")
        if self._stream.headers:
            fields = ",".join(f"{key}: {value}" for key, value in self._stream.headers.items())
            cmd.append(f"--http-header-fields={fields}")
        if self._stream.subtitle_url:
            cmd.append(f"--sub-file={self._stream.subtitle_url}")
        cmd.append(self._stream.url)
        return cmd

    def _process_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @work(thread=True)
    def _watch_process(self) -> None:
        assert self._process is not None
        self._process.wait()
        self.app.call_from_thread(self._finish)

    def _finish(self) -> None:
        if not self._stopped:
            self._stopped = True
            self.dismiss()

    def _poll(self) -> None:
        if self._ipc is None or not self._process_alive():
            return
        try:
            paused = bool(self._ipc.get_property("pause"))
            position = self._ipc.get_property("time-pos") or 0.0
            duration = self._ipc.get_property("duration")
            buffered = self._ipc.get_property("demuxer-cache-duration") or 0.0
            speed = self._ipc.get_property("cache-speed") or 0.0
        except MpvIPCError:
            return
        self.query_one(StreamHud).update_stats(
            paused=paused,
            position_seconds=float(position),
            duration_seconds=float(duration) if duration else None,
            buffered_seconds=float(buffered),
            cache_speed_bytes=float(speed),
        )

    def action_toggle_pause(self) -> None:
        self._send_command("cycle", "pause")

    def action_seek_back(self) -> None:
        self._send_command("seek", -10, "relative")

    def action_seek_forward(self) -> None:
        self._send_command("seek", 10, "relative")

    def _send_command(self, *args: object) -> None:
        if self._ipc is not None:
            with contextlib.suppress(MpvIPCError):
                self._ipc.command(*args)

    def action_stop(self) -> None:
        self._stopped = True
        if self._process is not None:
            terminate_group(self._process)
        self.dismiss()

    def on_unmount(self) -> None:
        if self._process is not None:
            terminate_group(self._process)
            unregister_process(self._process)
        if self._ipc is not None:
            self._ipc.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)
