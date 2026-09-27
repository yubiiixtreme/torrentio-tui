"""Signal-safe lifecycle for spawned player/streamer/downloader processes.

mpv, vlc, webtorrent/peerflix, and yt-dlp are all plain child processes
launched with subprocess. Left to Python's defaults, a Ctrl-C (SIGINT)
during playback either races with the child for the signal (both are in
the same foreground process group) or, if we ever swallow/ignore it,
leaves the child running as an orphan. `supervised_popen` puts this app
in charge instead: it starts the child in its own process group and, for
the lifetime of the `with` block, forwards SIGINT/SIGTERM/SIGHUP to that
group as a graceful terminate -- escalating to SIGKILL if the child
doesn't exit within a grace period -- so a Ctrl-C or app shutdown always
reaps the child cleanly instead of leaving it as a zombie or an orphaned
socket/port holder.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager

#: Grace period between a forwarded terminate signal and a hard kill.
TERMINATE_GRACE_SECONDS = 5.0

_FORWARDED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


@contextmanager
def supervised_popen(cmd: list[str], **popen_kwargs) -> Iterator[subprocess.Popen]:
    """Spawn `cmd` in its own process group and forward SIGINT/SIGTERM/
    SIGHUP to it for the duration of the `with` block. Always waits on
    the child before returning, even if a signal fired -- callers get a
    fully reaped process, never a zombie.
    """
    process = subprocess.Popen(cmd, start_new_session=True, **popen_kwargs)
    previous_handlers = install_signal_forwarding(process)
    try:
        yield process
    finally:
        restore_signal_handlers(previous_handlers)
        if process.poll() is None:
            process.wait()


def run_supervised(cmd: list[str], **popen_kwargs) -> subprocess.CompletedProcess:
    """`subprocess.run`-alike built on `supervised_popen`, for the common
    case of just blocking until the child exits."""
    with supervised_popen(cmd, **popen_kwargs) as process:
        stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)


def install_signal_forwarding(process: subprocess.Popen) -> dict[signal.Signals, object]:
    """Forward SIGINT/SIGTERM/SIGHUP to `process`'s group, returning the
    previous handlers so a caller managing the process across several
    event-loop ticks (rather than inside one `with` block) can restore
    them later via `restore_signal_handlers`."""
    return {
        sig: signal.signal(sig, lambda _signum, _frame: terminate_group(process))
        for sig in _FORWARDED_SIGNALS
    }


def restore_signal_handlers(previous: dict[signal.Signals, object]) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def terminate_group(process: subprocess.Popen) -> None:
    """Terminate `process`'s whole group, escalating to SIGKILL if it
    doesn't exit within `TERMINATE_GRACE_SECONDS`. Safe to call more than
    once, or after the process has already exited on its own."""
    if process.poll() is not None:
        return
    pgid = os.getpgid(process.pid)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGTERM)
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
