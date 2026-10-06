from __future__ import annotations

import contextlib
import json
import socket
import threading

import pytest

from torrentio_tui.player.mpv_ipc import MpvIPC, MpvIPCError


class _FakeMpvServer:
    """A minimal stand-in for mpv's JSON-IPC Unix socket server: accepts
    one connection at a time, replies to every `get_property`/command
    request with a canned value, and can be told to drop the connection
    once to exercise MpvIPC's reconnect path.
    """

    def __init__(self, socket_path, *, drop_first_connection: bool = False) -> None:
        self._socket_path = socket_path
        self._drop_first_connection = drop_first_connection
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(socket_path))
        self._server.listen(1)
        self._alive = True
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()

    def _serve_forever(self) -> None:
        connections_seen = 0
        while self._alive:
            self._server.settimeout(0.2)
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            connections_seen += 1
            if self._drop_first_connection and connections_seen == 1:
                conn.close()
                continue
            self._serve_connection(conn)

    def _serve_connection(self, conn: socket.socket) -> None:
        try:
            buffer = b""
            conn.settimeout(0.2)
            while self._alive:
                try:
                    chunk = conn.recv(4096)
                except TimeoutError:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                buffer += chunk
                while b"\n" in buffer:
                    line, _, buffer = buffer.partition(b"\n")
                    request = json.loads(line)
                    reply = {
                        "request_id": request["request_id"],
                        "error": "success",
                        "data": 42,
                    }
                    with contextlib.suppress(OSError):
                        conn.sendall((json.dumps(reply) + "\n").encode())
        finally:
            # Release the accepted socket promptly — otherwise it lingers
            # until GC and trips ResourceWarning: unclosed socket.
            with contextlib.suppress(OSError):
                conn.close()

    def stop(self) -> None:
        self._alive = False
        self._thread.join(timeout=2)
        self._server.close()


@pytest.fixture
def fake_mpv(tmp_path):
    socket_path = tmp_path / "mpv.sock"
    server = _FakeMpvServer(socket_path)
    yield socket_path
    server.stop()


def test_connect_and_get_property(fake_mpv):
    ipc = MpvIPC(fake_mpv, is_alive=lambda: True)
    ipc.connect(timeout=2.0)
    assert ipc.get_property("time-pos") == 42
    ipc.close()


def test_command_round_trip(fake_mpv):
    ipc = MpvIPC(fake_mpv, is_alive=lambda: True)
    ipc.connect(timeout=2.0)
    ipc.command("cycle", "pause")  # must not raise
    ipc.close()


def test_connect_times_out_if_socket_never_appears(tmp_path):
    ipc = MpvIPC(tmp_path / "nonexistent.sock", is_alive=lambda: True)
    with pytest.raises(MpvIPCError):
        ipc.connect(timeout=0.3)


def test_reconnects_transparently_after_dropped_connection(tmp_path):
    socket_path = tmp_path / "mpv.sock"
    server = _FakeMpvServer(socket_path, drop_first_connection=True)
    ipc = MpvIPC(socket_path, is_alive=lambda: True)
    try:
        ipc.connect(timeout=2.0)
        # First request's connection gets dropped by the server; get_property
        # must reconnect once and retry instead of raising.
        assert ipc.get_property("time-pos") == 42
    finally:
        ipc.close()
        server.stop()


def test_does_not_reconnect_once_process_has_exited(fake_mpv):
    ipc = MpvIPC(fake_mpv, is_alive=lambda: True)
    ipc.connect(timeout=2.0)
    ipc.close()  # simulate the socket having dropped
    ipc._is_alive = lambda: False  # and mpv itself is gone
    with pytest.raises(MpvIPCError, match="exited"):
        ipc.get_property("time-pos")
