"""Regression tests for the robustness/crash-fix batch.

Covers: corrupt JSON/TOML tolerance, atomic saves, registry wiring
(nhentai/rule34 + Stremio-subclass proxy passthrough), adult-source
payload guards, mpv IPC malformed replies, terminate_group races,
download header format, VLC header forwarding, and theme persistence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from contextlib import contextmanager

import pytest

from torrentio_tui.config import Config, save_theme
from torrentio_tui.history import HistoryStore
from torrentio_tui.library import LibraryStore
from torrentio_tui.models import StreamLink
from torrentio_tui.player import process as process_mod
from torrentio_tui.player.mpv_ipc import MpvIPC, MpvIPCError
from torrentio_tui.player.process import terminate_group
from torrentio_tui.sources import registry
from torrentio_tui.sources.adult import (
    HanimeSource,
    NHentaiSource,
    Rule34Source,
    _nhentai_cover,
    _nhentai_year,
)
from torrentio_tui.sources.base import SourceError


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Point XDG config/data/cache at tmp dirs so stores never touch ~."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    for var in (
        "TORRENTIO_TUI_STREAM_URL",
        "TORRENTIO_TUI_CINEMETA_URL",
        "TORRENTIO_TUI_TIMEOUT",
        "TORRENTIO_TUI_PROXY",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _adult_config() -> Config:
    cfg = Config()
    cfg.adult.enabled = True
    return cfg


class _FakeHTTPResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(payload: object):
    def _opener(request, timeout=None):
        return _FakeHTTPResponse(payload)

    return _opener


# -- history / library --------------------------------------------------------


def test_corrupt_history_json_starts_empty_and_backs_up(isolated_dirs):
    from torrentio_tui.config import history_file

    history_file().parent.mkdir(parents=True, exist_ok=True)
    history_file().write_text("{not valid json!!!")
    store = HistoryStore()  # must not raise
    assert store.recent() == []
    assert history_file().with_suffix(".json.corrupt").exists()


def test_corrupt_library_json_starts_empty(isolated_dirs):
    from torrentio_tui.config import library_file

    library_file().parent.mkdir(parents=True, exist_ok=True)
    library_file().write_text("[1, 2,")
    store = LibraryStore()  # must not raise
    assert store.all() == []


def test_history_save_is_valid_json_and_round_trips(isolated_dirs):
    from torrentio_tui.config import history_file

    store = HistoryStore()
    store.record(
        item_id="tt123",
        source_id="stremio",
        title="Dune",
        episode_label=None,
        position_seconds=10.0,
        duration_seconds=100.0,
    )
    assert json.loads(history_file().read_text())  # parses cleanly
    assert HistoryStore().recent()[0].title == "Dune"


# -- config -------------------------------------------------------------------


def test_malformed_config_toml_falls_back_to_defaults(isolated_dirs):
    from torrentio_tui.config import config_file

    config_file().parent.mkdir(parents=True, exist_ok=True)
    config_file().write_text("[[[this is not toml")
    cfg = Config.load()  # must not raise
    assert cfg.player.backend in ("mpv", "termux")
    assert isinstance(cfg.enabled_sources, list)


def test_string_enabled_sources_becomes_single_item_list(isolated_dirs):
    from torrentio_tui.config import config_file

    config_file().parent.mkdir(parents=True, exist_ok=True)
    config_file().write_text('[sources]\nenabled = "stremio"\n')
    assert Config.load().enabled_sources == ["stremio"]


def test_config_language_not_shared_between_instances():
    assert Config().language is not Config().language


def test_subtitle_language_names_resolve():
    assert Config().language.get_subtitle_language_names()[0] == "English"


def test_save_theme_handles_single_quotes(tmp_path, monkeypatch):
    import torrentio_tui.config as config_mod

    cfg = tmp_path / "config.toml"
    cfg.write_text("[ui]\ntheme = 'nord'\n")
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_theme("dracula")
    assert 'theme = "dracula"' in cfg.read_text()


def test_save_theme_adds_missing_ui_section(tmp_path, monkeypatch):
    import torrentio_tui.config as config_mod

    cfg = tmp_path / "config.toml"
    cfg.write_text('[player]\nbackend = "mpv"\n')
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_theme("nord")
    assert "[ui]" in cfg.read_text()
    assert 'theme = "nord"' in cfg.read_text()


def test_save_theme_does_not_touch_other_sections(tmp_path, monkeypatch):
    import torrentio_tui.config as config_mod

    cfg = tmp_path / "config.toml"
    cfg.write_text('[player]\nbackend = "mpv"\n\n[ui]\ntheme = "nord"\n')
    monkeypatch.setattr(config_mod, "config_file", lambda: cfg)
    save_theme("dracula")
    text = cfg.read_text()
    assert 'backend = "mpv"' in text
    assert text.count("theme = ") == 1


# -- process lifecycle --------------------------------------------------------


def test_terminate_group_on_exited_process_does_not_raise():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    terminate_group(proc)  # must not raise (used to race in getpgid)


def test_terminate_group_handles_reaped_pid_gracefully(monkeypatch):
    """Simulate the child vanishing between poll() and getpgid()."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    monkeypatch.setattr(
        process_mod.os, "getpgid", lambda pid: (_ for _ in ()).throw(ProcessLookupError())
    )
    terminate_group(proc)  # must not raise — runs inside a signal handler


# -- mpv IPC ------------------------------------------------------------------


def test_mpv_ipc_malformed_reply_raises_mpv_ipc_error(tmp_path):
    class _FakeSock:
        def __init__(self):
            self._sent = False

        def recv(self, n):
            if not self._sent:
                self._sent = True
                return b"this is not json\n"
            return b""

    ipc = MpvIPC(tmp_path / "mpv.sock", is_alive=lambda: True)
    ipc._sock = _FakeSock()
    with pytest.raises(MpvIPCError):
        ipc._await_reply(1)


# -- registry wiring ----------------------------------------------------------


def test_nhentai_and_rule34_are_registered():
    assert "nhentai" in registry.available_source_ids()
    assert "rule34" in registry.available_source_ids()


def test_comet_gets_proxy_and_custom_stream_url():
    cfg = Config()
    cfg.enabled_sources = ["comet"]
    cfg.network.proxy_url = "socks5://127.0.0.1:40000"
    cfg.sources_config = {"comet": {"stream_url": "https://comet.example.com"}}
    (source,) = registry.load_sources(cfg)
    assert source.stream_url == "https://comet.example.com"
    assert source.proxy_url == "socks5://127.0.0.1:40000"


def test_aiostreams_gets_proxy():
    cfg = Config()
    cfg.enabled_sources = ["aiostreams"]
    cfg.network.proxy_url = "http://127.0.0.1:8080"
    (source,) = registry.load_sources(cfg)
    assert source.proxy_url == "http://127.0.0.1:8080"


# -- adult sources ------------------------------------------------------------


def test_nhentai_year_handles_int_timestamp():
    import datetime

    ts = datetime.datetime(2021, 5, 4, tzinfo=datetime.timezone.utc).timestamp()
    assert _nhentai_year(int(ts)) == 2021
    assert _nhentai_year("2020-01-02") == 2020
    assert _nhentai_year(None) is None


def test_nhentai_cover_built_from_media_id():
    item = {"media_id": "12345", "images": {"thumbnail": {"t": "j"}}}
    assert _nhentai_cover(item) == "https://t.nhentai.net/galleries/12345/thumb.jpg"
    assert _nhentai_cover({}) == ""


def test_nhentai_search_handles_int_upload_date(monkeypatch):
    payload = {
        "result": [
            {
                "id": 42,
                "title": {"english": "Test Doujin"},
                "tags": [{"name": "tag1"}],
                "upload_date": 1620000000,
                "media_id": "999",
                "images": {"thumbnail": {"t": "p"}},
            }
        ]
    }
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(payload))
    results = NHentaiSource(config=_adult_config()).search("test")
    assert len(results) == 1
    assert isinstance(results[0].year, int)
    assert "t.nhentai.net" in results[0].poster_url


def test_rule34_dict_error_payload_raises_source_error(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen({"error": "oops"}))
    with pytest.raises(SourceError):
        Rule34Source(config=_adult_config()).search("test")


def test_hanime_skips_empty_src_urls(monkeypatch):
    payload = {"sources": [{"src": "", "height": 720}, {"src": "https://cdn/x.mp4", "height": 720}]}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(payload))
    from torrentio_tui.models import Episode, MediaKind, SearchResult

    item = SearchResult(id="hanime:show", title="Show", kind=MediaKind.ANIME, source_id="hanime")
    links = HanimeSource(config=_adult_config()).get_streams(
        item, Episode(id="hanime:ep1", title="E1")
    )
    assert [link.url for link in links] == ["https://cdn/x.mp4"]


# -- quality screen -----------------------------------------------------------


def test_subtitle_lang_name_lookup():
    from torrentio_tui.ui.screens.quality import SubtitleScreen

    screen = SubtitleScreen(Config().language)
    assert screen._get_lang_name("eng") == "English"
    assert screen._get_lang_name("jpn") == "Japanese"
    assert screen._get_lang_name("zzz") == "ZZZ"


# -- downloads / vlc ----------------------------------------------------------


def test_download_header_format_and_unicode_title(tmp_path, monkeypatch):
    import torrentio_tui.downloads as downloads_mod

    captured: dict = {}

    @contextmanager
    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd

        class _Proc:
            stdout = iter(["[download] 100% of 1MiB"])

            def wait(self):
                return 0

        yield _Proc()

    monkeypatch.setattr(downloads_mod, "supervised_popen", _fake_popen)
    monkeypatch.setattr(downloads_mod, "is_available", lambda: True)
    stream = StreamLink(url="https://cdn/x.mp4", quality="1080p", headers={"X-Foo": "bar"})
    downloads_mod.download(stream, "日本語タイトル", tmp_path)
    assert "--add-header" in captured["cmd"]
    idx = captured["cmd"].index("--add-header")
    assert captured["cmd"][idx + 1] == "X-Foo: bar"  # space after colon (yt-dlp format)
    out_idx = captured["cmd"].index("-o") + 1
    assert "日本語タイトル" in captured["cmd"][out_idx]  # not stripped to "video"


def test_vlc_forwards_auth_headers(monkeypatch):
    import torrentio_tui.player.vlc as vlc_mod

    captured: dict = {}

    class _Result:
        returncode = 0

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(vlc_mod, "run_supervised", _fake_run)
    stream = StreamLink(
        url="https://cdn/x.mp4",
        quality="1080p",
        headers={"Authorization": "Bearer abc", "Referer": "https://x/"},
    )
    assert vlc_mod.VlcPlayer().play(stream, title="T") == 0
    assert "--http-referrer=https://x/" in captured["cmd"]
    assert "--http-header=Authorization: Bearer abc" in captured["cmd"]


# -- cli ----------------------------------------------------------------------


def _write_config(sources: list[str]) -> None:
    from torrentio_tui.config import config_file

    config_file().parent.mkdir(parents=True, exist_ok=True)
    config_file().write_text(f"[sources]\nenabled = {sources!r}\n")


def test_main_reports_gated_adult_source_without_traceback(isolated_dirs, capsys):
    from torrentio_tui.cli import main

    _write_config(["hanime"])  # adult gate left disabled
    assert main([]) == 1
    captured = capsys.readouterr()
    assert "Adult content is disabled" in captured.err
    assert "Traceback" not in captured.err


def test_doctor_probes_registry_resolved_addons(isolated_dirs, monkeypatch):
    from torrentio_tui import cli as cli_mod

    probed: list[str] = []
    monkeypatch.setattr(
        cli_mod, "_check_reachable", lambda label, url, timeout, proxy: probed.append(url)
    )
    _write_config(["stremio"])
    assert cli_mod.run_doctor(offline=False) == 0
    assert any("manifest.json" in url for url in probed)
    assert any("torrentio" in url for url in probed)


def test_doctor_reports_gated_source_instead_of_crashing(isolated_dirs, capsys):
    from torrentio_tui import cli as cli_mod

    _write_config(["hanime"])  # adult gate left disabled
    assert cli_mod.run_doctor(offline=False) == 0
    assert "Source setup" in capsys.readouterr().out
