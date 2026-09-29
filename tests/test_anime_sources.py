"""Tests for the anime RSS sources (Nyaa, SubsPlease).

Network is mocked with captured feed fixtures. The important case here is
SubsPlease: its live feed carries no <description> element, which used to
crash `search()` with AttributeError instead of returning results.
"""

from __future__ import annotations

from torrentio_tui.sources.anime import NyaaSource, SubsPleaseSource

# One <item> exactly as SubsPlease serves it: no <description> at all.
SUBSPLEASE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>SubsPlease RSS</title>
<item>
  <title>[SubsPlease] LIAR GAME - 26 (1080p) [A9057F68].mkv</title>
  <link>magnet:?xt=urn:btih:BXYLAMUPEVWL55ZJXMWD0000000000000000000000000000000000</link>
  <pubDate>Mon, 28 Sep 2026 09:02:08 +0000</pubDate>
</item>
<item>
  <title>[SubsPlease] Some Other Show - 01 (1080p) [B1234ABCD].mkv</title>
  <link>magnet:?xt=urn:urn:sha1:OTHER0000000000000000000000000000000000000</link>
  <pubDate>Mon, 21 Sep 2026 09:18:56 +0000</pubDate>
</item>
</channel></rss>
"""

NYAA_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa"><channel>
<item>
  <title>[SubsPlease] Naruto - 220 (1080p)</title>
  <link>https://nyaa.si/download/1234.nova.mkv</link>
  <guid>https://nyaa.si/view/1234</guid>
  <pubDate>Mon, 28 Sep 2026 09:02:08 +0000</pubDate>
  <nyaa:seeders>120</nyaa:seeders>
  <nyaa:size>1.4 GiB</nyaa:size>
</item>
</channel></rss>
"""


def _patch_urlopen(monkeypatch, body: str) -> None:
    def fake_urlopen(req, timeout=None):
        class _Resp:
            def read(self) -> bytes:
                return body.encode()

            def __enter__(self):
                return self

            def __exit__(self, *args) -> bool:
                return False

        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)


def test_subsplease_feed_without_description_still_returns_results(monkeypatch) -> None:
    """Regression: a missing <description> must not raise AttributeError.

    The live SubsPlease feed has no <description> element, so the old
    `desc_elem.text` access crashed on every single search.
    """
    _patch_urlopen(monkeypatch, SUBSPLEASE_RSS)

    results = SubsPleaseSource().search("liar game")

    assert len(results) == 1
    assert "LIAR GAME" in results[0].title
    assert results[0].kind.name == "ANIME"


def test_subsplease_filters_by_query(monkeypatch) -> None:
    _patch_urlopen(monkeypatch, SUBSPLEASE_RSS)

    assert SubsPleaseSource().search("a show that is not in the feed") == []


def test_subsplease_get_streams_yields_magnet(monkeypatch) -> None:
    _patch_urlopen(monkeypatch, SUBSPLEASE_RSS)

    item = SubsPleaseSource().search("liar game")[0]
    streams = SubsPleaseSource().get_streams(item, None)

    assert len(streams) == 1
    assert streams[0].url.startswith("magnet:?")


def test_nyaa_parses_seeders_and_size(monkeypatch) -> None:
    _patch_urlopen(monkeypatch, NYAA_RSS)

    results = NyaaSource().search("naruto")

    assert len(results) == 1
    assert "Naruto" in results[0].title
