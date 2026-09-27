"""Custom theme loading: drop a JSON file under
~/.config/torrentio-tui/themes/ and it shows up alongside the built-ins
in the theme cycle ("t") and the command palette (Ctrl+P -> "theme") --
no code changes, and no restart needed to pick up edits, since the
themes directory is re-scanned every time the cycle/palette is used.

File format (every field but "name" is optional -- omitted colors fall
back to Textual's own theme defaults):

    {
      "name": "my-theme",
      "dark": true,
      "primary": "#F5C518",
      "secondary": "#A855F7",
      "accent": "#E11D48",
      "warning": "#F5C518",
      "error": "#EF4444",
      "success": "#22C55E",
      "foreground": "#F4F4F5",
      "background": "#0F172A",
      "surface": "#1E293B",
      "panel": "#1E293B",
      "boost": "#334155"
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from textual.theme import Theme

from torrentio_tui.config import config_dir

_THEME_COLOR_FIELDS = (
    "primary",
    "secondary",
    "accent",
    "warning",
    "error",
    "success",
    "foreground",
    "background",
    "surface",
    "panel",
    "boost",
)


class ThemeLoadError(Exception):
    pass


def themes_dir() -> Path:
    return config_dir() / "themes"


def _parse_theme_file(path: Path) -> Theme:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemeLoadError(f"{path.name}: {exc}") from exc

    name = data.get("name") or path.stem
    kwargs = {field: data[field] for field in _THEME_COLOR_FIELDS if field in data}
    try:
        return Theme(name=name, dark=bool(data.get("dark", True)), **kwargs)
    except (TypeError, ValueError) as exc:
        raise ThemeLoadError(f"{path.name}: {exc}") from exc


def load_custom_themes() -> list[Theme]:
    """Parse every `*.json` file under `themes_dir()` into a `Theme`.
    A malformed file is skipped rather than failing the whole app --
    the rest of the themes (and the app itself) still load."""
    directory = themes_dir()
    if not directory.is_dir():
        return []

    themes = []
    for path in sorted(directory.glob("*.json")):
        try:
            themes.append(_parse_theme_file(path))
        except ThemeLoadError:
            continue
    return themes
