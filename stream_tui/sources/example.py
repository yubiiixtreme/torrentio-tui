"""TEMPLATE — copy this file to build a real source. Not registered by
default and not usable as-is.

This is where site-specific work belongs: HTTP calls, HTML/JSON parsing,
extractor logic for whatever site you have the rights to pull from, and any
auth/cookies it needs. Keep all of that contained to this class — the UI,
player, history, and download code never need to change.

Legal/ethical note (read before filling this in): only point this at
sources you have the right to access/redistribute through (an API you have
a license for, content you own, sites whose ToS permit this kind of
automated access, etc). This scaffold intentionally ships with no real
scraper wired in.
"""
from __future__ import annotations

from stream_tui.models import Episode, MediaKind, SearchResult, StreamLink
from stream_tui.sources.base import Source, SourceError


class ExampleSource(Source):
    id = "example"
    name = "Example Source"

    def __init__(self) -> None:
        # e.g. self.session = requests.Session(); self.base_url = "https://..."
        pass

    def search(self, query: str) -> list[SearchResult]:
        # TODO: call your site/API, parse results into SearchResult objects.
        #
        # try:
        #     resp = self.session.get(f"{self.base_url}/search", params={"q": query}, timeout=10)
        #     resp.raise_for_status()
        # except requests.RequestException as exc:
        #     raise SourceError(f"{self.name} search failed: {exc}") from exc
        #
        # return [
        #     SearchResult(id=row["id"], title=row["title"], kind=MediaKind.MOVIE, source_id=self.id)
        #     for row in resp.json()["results"]
        # ]
        raise SourceError("ExampleSource is a template — implement search() first")

    def get_episodes(self, item: SearchResult) -> list[Episode]:
        # TODO: only needed for MediaKind.SERIES; return one Episode per
        # season/number. Movies can rely on the base class default.
        return super().get_episodes(item)

    def get_streams(self, item: SearchResult, episode: Episode) -> list[StreamLink]:
        # TODO: resolve the actual playable URL(s) here. Many sites require
        # specific headers (Referer/User-Agent/Origin) for the CDN to accept
        # the request — attach them via StreamLink.headers rather than
        # baking them into the player backend.
        #
        # return [
        #     StreamLink(url=hls_url, quality="1080p", headers={"Referer": self.base_url}),
        # ]
        raise SourceError("ExampleSource is a template — implement get_streams() first")
