from __future__ import annotations

import signal
import subprocess
import sys
import threading

import pytest

from torrentio_tui.player import process as process_mod
from torrentio_tui.player.process import (
    ensure_signal_handlers_installed,
    run_supervised,
    supervised_popen,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Every test gets a clean, empty registry -- state here is global
    module state (that's the whole point: one process-wide handler)."""
    process_mod._active_processes.clear()
    yield
    process_mod._active_processes.clear()


def test_run_supervised_returns_exit_code():
    result = run_supervised([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3


def test_run_supervised_captures_piped_output():
    result = run_supervised(
        [sys.executable, "-c", "print('hello')"], stdout=subprocess.PIPE, text=True
    )
    assert result.stdout == "hello\n"
    assert result.returncode == 0


def test_supervised_popen_leaves_no_zombie():
    with supervised_popen([sys.executable, "-c", "pass"]) as process:
        pass
    assert process.returncode is not None


def test_process_is_registered_only_for_the_lifetime_of_the_with_block():
    with supervised_popen([sys.executable, "-c", "pass"]) as process:
        assert process in process_mod._active_processes
    assert process not in process_mod._active_processes


def test_handlers_install_exactly_once(monkeypatch):
    monkeypatch.setattr(process_mod, "_handlers_installed", False)
    calls = []
    monkeypatch.setattr(signal, "signal", lambda sig, handler: calls.append(sig) or signal.SIG_DFL)
    ensure_signal_handlers_installed()
    ensure_signal_handlers_installed()
    assert len(calls) == len(process_mod._FORWARDED_SIGNALS)  # only the first call did anything


def test_signal_from_a_worker_thread_does_not_raise(monkeypatch):
    """Regression: signal.signal() only works on the main thread. The
    download flow runs via Textual's @work(thread=True), which calls
    straight into run_supervised() from a real background thread --
    this used to crash every single download with
    `ValueError: signal only works in main thread of the main interpreter`.
    """
    monkeypatch.setattr(process_mod, "_handlers_installed", False)
    ensure_signal_handlers_installed()  # simulates cli.main()'s startup call

    error: dict[str, BaseException] = {}

    def worker() -> None:
        try:
            run_supervised([sys.executable, "-c", "pass"])
        except BaseException as exc:  # noqa: BLE001 -- must capture anything, this is the test
            error["exc"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert "exc" not in error, f"run_supervised() raised from a worker thread: {error.get('exc')}"


def test_signal_from_a_worker_thread_before_any_main_thread_call_still_works(monkeypatch):
    """Even if a worker thread is the very first caller in the process's
    lifetime (handlers never installed yet, and can't be installed from
    here), it must still just run the process rather than raising."""
    monkeypatch.setattr(process_mod, "_handlers_installed", False)

    error: dict[str, BaseException] = {}

    def worker() -> None:
        try:
            result = run_supervised([sys.executable, "-c", "import sys; sys.exit(0)"])
            assert result.returncode == 0
        except BaseException as exc:  # noqa: BLE001
            error["exc"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert "exc" not in error


def test_signal_handler_terminates_every_registered_process(monkeypatch):
    calls = []
    monkeypatch.setattr(process_mod, "terminate_group", calls.append)

    with supervised_popen([sys.executable, "-c", "import time; time.sleep(0.05)"]) as process:
        process_mod._handle_signal(signal.SIGTERM, None)

    assert calls == [process]


def test_signal_handler_falls_through_to_previous_when_nothing_registered(monkeypatch):
    """With nothing of ours running, the signal wasn't "ours" -- it must
    replay whatever was registered before us instead of silently eating
    Ctrl-C for the rest of the app's life."""
    replayed = []
    monkeypatch.setitem(
        process_mod._previous_handlers,
        signal.SIGTERM,
        lambda signum, frame: replayed.append(signum),
    )
    process_mod._handle_signal(signal.SIGTERM, None)
    assert replayed == [signal.SIGTERM]
