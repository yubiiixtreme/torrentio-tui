"""Optional outbound proxy support.

Torrentio's public instance Cloudflare-blocks some datacenter/VPN IP
ranges (HTTP 403) — see `sources/stremio.py`. Routing requests through a
proxy sidesteps that without needing a residential IP or a self-hosted
Torrentio. Typical use: Cloudflare WARP's local proxy mode.

    # one-time, starts a local SOCKS5 proxy on 127.0.0.1:40000
    warp-cli mode proxy
    warp-cli connect

Configure via `network.proxy_url` in config.toml, or `TORRENTIO_TUI_PROXY` /
`--proxy`:

    proxy_url = "socks5://127.0.0.1:40000"   # Cloudflare WARP proxy mode
    proxy_url = "http://127.0.0.1:8080"      # a plain HTTP/HTTPS proxy

http(s):// proxies work out of the box (stdlib). socks5(h):// / socks4://
proxies need the optional `pysocks` dependency: `pip install pysocks`, or
install this package as `torrentio-tui[proxy]`.
"""

from __future__ import annotations

import contextlib
import socket
import urllib.parse
import urllib.request
from collections.abc import Iterator

_SOCKS_SCHEMES = ("socks5", "socks5h", "socks4")


class ProxyError(Exception):
    pass


def build_opener(proxy_url: str | None) -> urllib.request.OpenerDirector:
    """Opener that applies an http(s):// proxy via urllib's ProxyHandler.
    socks5/socks4 proxies aren't handled here — see `socks_proxy()`."""
    if not proxy_url:
        return urllib.request.build_opener()
    scheme = urllib.parse.urlsplit(proxy_url).scheme.lower()
    if scheme in ("http", "https"):
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    if scheme in _SOCKS_SCHEMES:
        return urllib.request.build_opener()
    raise ProxyError(
        f"Unsupported proxy scheme {scheme!r} in {proxy_url!r} "
        "(use http://, https://, socks5://, socks5h://, or socks4://)"
    )


@contextlib.contextmanager
def socks_proxy(proxy_url: str | None) -> Iterator[None]:
    """Temporarily route stdlib sockets through a SOCKS proxy for the
    duration of the `with` block. No-op for empty/non-socks URLs.

    Scoped narrowly (patches `socket.socket`, restores it in `finally`)
    around a single blocking HTTP call, which is safe here because the
    call it wraps runs synchronously on Textual's event loop — nothing
    else touches sockets during that window.
    """
    if not proxy_url:
        yield
        return
    parsed = urllib.parse.urlsplit(proxy_url)
    scheme = parsed.scheme.lower()
    if scheme not in _SOCKS_SCHEMES:
        yield
        return

    try:
        import socks  # PySocks
    except ImportError as exc:
        raise ProxyError(
            f"{scheme}:// proxy configured but PySocks isn't installed. "
            "Install it with: pip install pysocks"
        ) from exc

    proxy_type = socks.SOCKS4 if scheme == "socks4" else socks.SOCKS5
    original_socket = socket.socket
    socks.set_default_proxy(
        proxy_type,
        parsed.hostname,
        parsed.port or 1080,
        rdns=scheme == "socks5h",
        username=parsed.username,
        password=parsed.password,
    )
    socket.socket = socks.socksocket
    try:
        yield
    finally:
        socket.socket = original_socket


def pysocks_available() -> bool:
    try:
        import socks  # noqa: F401
    except ImportError:
        return False
    return True


def open_url(
    url: str,
    timeout: float,
    proxy_url: str | None = None,
    headers: dict[str, str] | None = None,
):
    """GET `url`, honoring an optional proxy, and return the open response
    (a context manager, as `urllib.request.urlopen()` returns). Lets
    `urllib.error.HTTPError`/`URLError` propagate — callers translate those
    into their own domain-specific errors.

    Only builds a dedicated opener when an http(s) proxy is configured;
    otherwise calls `urllib.request.urlopen()` directly, so callers that
    need to unit-test this without a real proxy can still monkeypatch that
    module-level function.
    """
    req = urllib.request.Request(url, headers=headers or {})
    scheme = urllib.parse.urlsplit(proxy_url).scheme.lower() if proxy_url else ""
    opener_open = build_opener(proxy_url).open if scheme in ("http", "https") else None
    with socks_proxy(proxy_url):
        if opener_open:
            return opener_open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)
