from pathlib import Path

from torrentio_tui.models import MediaKind
from torrentio_tui.sources.local import LocalSource


def test_search_finds_video_files(tmp_path: Path) -> None:
    (tmp_path / "Some Movie.mp4").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")

    source = LocalSource(root=tmp_path)
    results = source.search("movie")

    assert len(results) == 1
    assert results[0].title == "Some Movie"
    assert results[0].kind == MediaKind.MOVIE


def test_search_empty_query_returns_all(tmp_path: Path) -> None:
    (tmp_path / "a.mkv").write_bytes(b"")
    (tmp_path / "b.mkv").write_bytes(b"")

    source = LocalSource(root=tmp_path)
    assert len(source.search("")) == 2


def test_get_streams_returns_local_path(tmp_path: Path) -> None:
    video = tmp_path / "a.mp4"
    video.write_bytes(b"")

    source = LocalSource(root=tmp_path)
    [item] = source.search("a")
    [stream] = source.get_streams(item, source.get_episodes(item)[0])

    assert stream.url == str(video)
    assert stream.quality == "local"
