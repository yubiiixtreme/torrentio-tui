from __future__ import annotations

from torrentio_tui.ui.screens.main import _format_download_progress


def test_parses_percent_speed_and_eta():
    line = "[download]  42.3% of  700.00MiB at    5.00MiB/s ETA 00:30"
    assert (
        _format_download_progress("My Movie", line) == "⏳ My Movie — 42.3%  5.00MiB/s  ETA 00:30"
    )


def test_parses_percent_only_when_speed_and_eta_absent():
    line = "[download] 100% of  700.00MiB in 00:02:12"
    assert _format_download_progress("My Movie", line) == "⏳ My Movie — 100%"


def test_ignores_unrelated_yt_dlp_output():
    assert _format_download_progress("My Movie", "[youtube] Extracting URL: https://x") is None
    assert _format_download_progress("My Movie", "") is None
