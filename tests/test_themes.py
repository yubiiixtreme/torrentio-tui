from __future__ import annotations

import json
from pathlib import Path

import pytest

from torrentio_tui import themes as themes_mod
from torrentio_tui.config import Config
from torrentio_tui.sources.local import LocalSource
from torrentio_tui.themes import load_custom_themes
from torrentio_tui.ui.app import TorrentioTuiApp


@pytest.fixture
def fake_themes_dir(tmp_path, monkeypatch):
    directory = tmp_path / "themes"
    directory.mkdir()
    monkeypatch.setattr(themes_mod, "themes_dir", lambda: directory)
    return directory


def test_load_custom_themes_empty_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(themes_mod, "themes_dir", lambda: tmp_path / "nonexistent")
    assert load_custom_themes() == []


def test_loads_a_well_formed_theme(fake_themes_dir):
    (fake_themes_dir / "sunset.json").write_text(
        json.dumps(
            {
                "name": "sunset",
                "primary": "#FF8800",
                "background": "#111111",
                "dark": True,
            }
        )
    )
    loaded = load_custom_themes()
    assert len(loaded) == 1
    assert loaded[0].name == "sunset"
    assert loaded[0].primary == "#FF8800"


def test_name_falls_back_to_filename_stem(fake_themes_dir):
    (fake_themes_dir / "my-cool-theme.json").write_text(json.dumps({"primary": "#ABCDEF"}))
    loaded = load_custom_themes()
    assert loaded[0].name == "my-cool-theme"


def test_malformed_json_is_skipped_not_fatal(fake_themes_dir):
    (fake_themes_dir / "broken.json").write_text("{not valid json")
    (fake_themes_dir / "good.json").write_text(json.dumps({"name": "good", "primary": "#FFFFFF"}))
    loaded = load_custom_themes()
    assert [t.name for t in loaded] == ["good"]


def test_unknown_field_is_skipped_not_fatal(fake_themes_dir):
    (fake_themes_dir / "bad-field.json").write_text(
        json.dumps({"name": "bad", "not_a_real_field": "#FFFFFF"})
    )
    assert load_custom_themes() == []


@pytest.mark.asyncio
async def test_app_registers_builtin_and_custom_themes(fake_themes_dir, tmp_path: Path) -> None:
    (fake_themes_dir / "sunset.json").write_text(json.dumps({"name": "sunset", "primary": "#F80"}))

    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "torrentio" in app.available_themes
        assert "oled-black" in app.available_themes
        assert "sunset" in app.available_themes


@pytest.mark.asyncio
async def test_theme_cycle_includes_newly_added_custom_theme(
    fake_themes_dir, tmp_path: Path
) -> None:
    app = TorrentioTuiApp([LocalSource(root=tmp_path)], Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        # Drop a new theme file *after* the app already started.
        (fake_themes_dir / "midnight.json").write_text(
            json.dumps({"name": "midnight", "primary": "#123456"})
        )

        seen = set()
        for _ in range(20):
            app.screen.action_cycle_theme()
            await pilot.pause()
            seen.add(app.theme)
            if "midnight" in seen:
                break

        assert "midnight" in seen, "custom theme added after startup never appeared in the cycle"
