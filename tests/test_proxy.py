import socket

import pytest

from torrentio_tui.proxy import ProxyError, build_opener, socks_proxy


def test_build_opener_no_proxy_returns_default():
    opener = build_opener(None)
    assert opener is not None


def test_build_opener_http_proxy():
    opener = build_opener("http://127.0.0.1:8080")
    handler_types = {type(h).__name__ for h in opener.handlers}
    assert "ProxyHandler" in handler_types


def test_build_opener_unsupported_scheme_raises():
    with pytest.raises(ProxyError):
        build_opener("ftp://127.0.0.1:21")


def test_socks_proxy_noop_for_none():
    original = socket.socket
    with socks_proxy(None):
        assert socket.socket is original
    assert socket.socket is original


def test_socks_proxy_noop_for_http_url():
    original = socket.socket
    with socks_proxy("http://127.0.0.1:8080"):
        assert socket.socket is original
    assert socket.socket is original


def test_socks_proxy_restores_socket_on_exception():
    original = socket.socket
    pytest.importorskip("socks")

    def _boom():
        with socks_proxy("socks5://127.0.0.1:40000"):
            assert socket.socket is not original
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _boom()
    assert socket.socket is original
