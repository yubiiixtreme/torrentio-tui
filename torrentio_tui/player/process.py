"""Signal-safe lifecycle for spawned player/streamer/downloader processes.

mpv, vlc, webtorrent/peerflix, and yt-dlp are all plain child processes
launched with subprocess. Left to Python's defaults, a Ctrl-C (SIGINT)
during playback either races with the child for the signal (both are in
the same foreground process group) or, if we ever swallow/ignore it,
leaves the child running as an orphan. `supervised_popen` puts this app
in charge instead: it starts the child in its own process group and
registers it in a shared registry for as long as the `with` block is
open; one process-wide signal handler (installed once) forwards SIGINT/
SIGTERM/SIGHUP to every currently-registered child's group as a graceful
terminate -- escalating to SIGKILL if a child doesn't exit within a
grace period -- so a Ctrl-C or app shutdown always reaps every child
cleanly instead of leaving one as a zombie or an orphaned socket/port
holder.

A single process-wide handler (rather than one installed-and-restored
per call) is what makes this safe when more than one process is
supervised at once -- e.g. a download running while a HUD playback is
also active -- since two independent install/restore pairs would
otherwise clobber each other's "previous handler". It's also what makes
this safe to call from a worker thread: `signal.signal()` only works on
the main thread (calling it elsewhere raises `ValueError`), which the
download flow hits directly since it runs via Textual's
`@work(thread=True)`. `ensure_signal_handlers_installed()` is called
once at startup (see `cli.py`) so the handler is always in place by the
time any supervised process -- main-thread or not -- registers itself;
`supervised_popen` also attempts it itself as a fallback for direct
callers (tests, a library use of this module) that skip `cli.main()`.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

#: Grace period between a forwarded terminate signal and a hard kill.
TERMINATE_GRACE_SECONDS = 5.0

_FORWARDED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)

_active_processes: set[subprocess.Popen] = set()
_registry_lock = threading.Lock()
_previous_handlers: dict[signal.Signals, object] = {}
_handlers_installed = False


def ensure_signal_handlers_installed() -> None:
    """Install the process-wide SIGINT/SIGTERM/SIGHUP handler, once. A
    no-op after the first call, and a no-op (not an error) if called
    from a non-main thread before that -- the first main-thread caller
    installs it; callers before that point just don't get the custom
    handling yet (default Python signal behavior still applies, so
    nothing is broken, just not enhanced)."""
    global _handlers_installed
    if _handlers_installed or threading.current_thread() is not threading.main_thread():
        return
    for sig in _FORWARDED_SIGNALS:
        _previous_handlers[sig] = signal.signal(sig, _handle_signal)
    _handlers_installed = True


def _handle_signal(signum: int, frame: FrameType | None) -> None:
    with _registry_lock:
        processes = list(_active_processes)
    for process in processes:
        terminate_group(process)
    if processes:
        return
    # Nothing of ours was running, so this signal wasn't "ours" -- replay
    # whatever was registered before us (Python's own default_int_handler
    # for Ctrl-C, SIG_DFL for SIGTERM/SIGHUP) instead of silently eating it.
    previous = _previous_handlers.get(signum, signal.SIG_DFL)
    if callable(previous):
        previous(signum, frame)
    else:
        signal.signal(signum, previous)
        os.kill(os.getpid(), signum)
        signal.signal(signum, _handle_signal)


@contextmanager
def supervised_popen(cmd: list[str], **popen_kwargs) -> Iterator[subprocess.Popen]:
    """Spawn `cmd` in its own process group and register it so the
    shared signal handler forwards SIGINT/SIGTERM/SIGHUP to it for the
    duration of the `with` block. Always waits on the child before
    returning, even if a signal fired -- callers get a fully reaped
    process, never a zombie.
    """
    ensure_signal_handlers_installed()
    process = subprocess.Popen(cmd, start_new_session=True, **popen_kwargs)
    register_process(process)
    try:
        yield process
    finally:
        unregister_process(process)
        if process.poll() is None:
            process.wait()


def run_supervised(cmd: list[str], **popen_kwargs) -> subprocess.CompletedProcess:
    """`subprocess.run`-alike built on `supervised_popen`, for the common
    case of just blocking until the child exits."""
    with supervised_popen(cmd, **popen_kwargs) as process:
        stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)


def register_process(process: subprocess.Popen) -> None:
    """Add `process` to the set the shared signal handler forwards to.
    For callers (like the HUD playback screen) that manage a process
    across several event-loop ticks rather than inside one `with` block;
    `supervised_popen` calls this itself. Thread-safe."""
    with _registry_lock:
        _active_processes.add(process)


def unregister_process(process: subprocess.Popen) -> None:
    with _registry_lock:
        _active_processes.discard(process)


def terminate_group(process: subprocess.Popen) -> None:
    """Terminate `process`'s whole group, escalating to SIGKILL if it
    doesn't exit within `TERMINATE_GRACE_SECONDS`. Safe to call more than
    once, or after the process has already exited on its own."""
    if process.poll() is not None:
        return
    try:
        pgid = os.getpgid(process.pid)
    except (ProcessLookupError, OSError):
        # Child already reaped/exited between poll() and getpgid() — in
        # particular this runs inside a signal handler, where raising
        # would be fatal. Nothing left to terminate.
        return
    with contextlib.suppress(ProcessLookupError, OSError):
        os.killpg(pgid, signal.SIGTERM)
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.killpg(pgid, signal.SIGKILL)
