"""Regression test for a real bug found by inspecting textual-image's
source: on the Kitty Graphics Protocol (kitty, WezTerm, Ghostty, ...), a
placed image is only deleted from the terminal by textual-image's own
`Image.image = None` setter -- a plain Textual `widget.remove()` skips
that entirely, so swapping posters (or falling back to the icon card)
used to leave the previous poster's pixels ghosted on screen.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from torrentio_tui import images
from torrentio_tui.images import PosterWidget


class _FakeImageWidget(Static):
    """Stands in for textual_image's real `Image` widget: tracks whether
    `.image` was set to None (the real widget's ghost-cleanup trigger)
    before the widget was removed from the DOM."""

    def __init__(self, path) -> None:
        super().__init__()
        self._image = path
        self.cleared_before_remove = False

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value) -> None:
        self._image = value
        if value is None:
            self.cleared_before_remove = True


@pytest.fixture
def fake_image_widget(monkeypatch):
    monkeypatch.setattr(images, "_ImageWidget", _FakeImageWidget)
    monkeypatch.setattr(images, "IMAGES_AVAILABLE", True)
    return _FakeImageWidget


@pytest.mark.asyncio
async def test_swapping_posters_clears_old_image_before_removal(fake_image_widget) -> None:
    from textual.app import App

    class _HarnessApp(App):
        def compose(self):
            yield PosterWidget(id="poster")

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        poster = app.query_one(PosterWidget)

        poster.show_image("poster-one.jpg")
        await pilot.pause()
        first = poster.query_one(fake_image_widget)
        assert first.image == "poster-one.jpg"

        poster.show_image("poster-two.jpg")
        await pilot.pause()

        assert first.cleared_before_remove, (
            "the old poster's Kitty-protocol image was never cleared -- "
            "it stays ghosted on screen instead of being deleted"
        )
        second = poster.query_one(fake_image_widget)
        assert second.image == "poster-two.jpg"


@pytest.mark.asyncio
async def test_falling_back_to_icon_clears_old_image(fake_image_widget) -> None:
    from textual.app import App

    class _HarnessApp(App):
        def compose(self):
            yield PosterWidget(id="poster")

    app = _HarnessApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        poster = app.query_one(PosterWidget)

        poster.show_image("poster-one.jpg")
        await pilot.pause()
        shown = poster.query_one(fake_image_widget)

        poster.show_fallback("🍿")
        await pilot.pause()

        assert shown.cleared_before_remove
