from __future__ import annotations

import signal
import sys

from torrentio_tui.player.process import run_supervised, supervised_popen


def test_run_supervised_returns_exit_code():
    result = run_supervised([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3


def test_run_supervised_captures_piped_output():
    result = run_supervised(
        [sys.executable, "-c", "print('hello')"],
        stdout=__import__("subprocess").PIPE,
        text=True,
    )
    assert result.stdout == "hello\n"
    assert result.returncode == 0


def test_supervised_popen_restores_previous_signal_handler():
    original = signal.getsignal(signal.SIGINT)
    with supervised_popen([sys.executable, "-c", "pass"]) as process:
        assert signal.getsignal(signal.SIGINT) is not original
        process.wait()
    assert signal.getsignal(signal.SIGINT) is original


def test_supervised_popen_leaves_no_zombie():
    with supervised_popen([sys.executable, "-c", "pass"]) as process:
        pass
    assert process.returncode is not None
