"""End-to-end regression test for a real bug: `MainScreen._run_download`
runs via Textual's `@work(thread=True)` -- a genuine background OS
thread, not just an asyncio task -- and calls straight into
`downloads.download()`. `download()` uses `supervised_popen`, which used
to call `signal.signal()` directly on every invocation; Python only
allows that from the main thread, so every single download attempt
raised `ValueError: signal only works in main thread of the main
interpreter` instead of downloading anything. Fixed by installing one
process-wide signal handler up front (see `player/process.py`) instead
of installing/restoring one per call.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

from torrentio_tui import downloads
from torrentio_tui.models import StreamLink
from torrentio_tui.player import process as process_mod


@pytest.fixture(autouse=True)
def _reset_registry():
    process_mod._active_processes.clear()
    yield
    process_mod._active_processes.clear()


@pytest.fixture
def fake_yt_dlp_on_path(monkeypatch, tmp_path):
    """A real, runnable script literally named "yt-dlp" on PATH -- so
    `subprocess.Popen(["yt-dlp", ...])`'s own PATH lookup finds it, the
    same way it would find the real tool. Avoids mocking subprocess/
    shutil internals, which would only test the mock, not the real
    argv[0]-lookup path the app actually depends on.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "yt-dlp"
    script.write_text(f"#!{sys.executable}\nprint('[download] 100%% of 1.00MiB')\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return script


def test_download_from_a_background_thread_does_not_raise(fake_yt_dlp_on_path, tmp_path):
    stream = StreamLink(url="https://example.com/video.mp4", quality="1080p")
    result: dict[str, object] = {}

    def worker() -> None:
        try:
            dest = downloads.download(stream, "My Video", tmp_path / "out")
            result["dest"] = dest
        except BaseException as exc:  # noqa: BLE001 -- must capture anything for the assertion
            result["exc"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert "exc" not in result, f"download() raised from a worker thread: {result.get('exc')}"
    assert result["dest"] == tmp_path / "out"
