from __future__ import annotations

from torrentio_tui import images


def test_download_image_rejects_non_image_payload(monkeypatch, tmp_path):
    """An HTML error page (common when a poster URL 404s) must not get
    written to the cache and treated as a valid image."""
    monkeypatch.setattr(images, "IMAGE_CACHE_DIR", tmp_path)

    class FakeResp:
        def read(self):
            return b"<html>not an image</html>"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(images.urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    assert images.download_image("https://example.com/poster.jpg") is None
    assert list(tmp_path.glob("*")) == []


def test_download_image_accepts_real_jpeg_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(images, "IMAGE_CACHE_DIR", tmp_path)
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20

    class FakeResp:
        def read(self):
            return jpeg_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(images.urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    path = images.download_image("https://example.com/poster.jpg")
    assert path is not None
    assert path.read_bytes() == jpeg_bytes

    # Second call hits the cache -- no network call needed.
    monkeypatch.setattr(
        images.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not re-fetch")),
    )
    assert images.download_image("https://example.com/poster.jpg") == path


def test_download_image_retries_transient_failure_then_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(images, "IMAGE_CACHE_DIR", tmp_path)
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    calls = {"n": 0}

    class FakeResp:
        def read(self):
            return jpeg_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def flaky_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("slow network")
        return FakeResp()

    monkeypatch.setattr(images.urllib.request, "urlopen", flaky_urlopen)
    path = images.download_image("https://example.com/poster.jpg")
    assert path is not None
    assert path.read_bytes() == jpeg_bytes
    assert calls["n"] == 3


def test_download_image_does_not_retry_404(monkeypatch, tmp_path):
    import urllib.error

    monkeypatch.setattr(images, "IMAGE_CACHE_DIR", tmp_path)
    calls = {"n": 0}

    def not_found(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(images.urllib.request, "urlopen", not_found)
    assert images.download_image("https://example.com/missing.jpg") is None
    assert calls["n"] == 1
