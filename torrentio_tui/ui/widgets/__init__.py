"""Shared widgets used across screens."""

from __future__ import annotations

from textual.widgets import ListView

__all__ = ["VimListView"]


class VimListView(ListView):
    """`ListView` with j/k added alongside the built-in up/down -- every
    list in the app (search results, episodes, quality picker, ...) gets
    vim-style navigation for free just by using this instead of `ListView`.
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]
