"""Client for mpv's JSON IPC protocol over a Unix domain socket
(--input-ipc-server=<path>): https://mpv.io/manual/stable/#json-ipc

Used to read live playback stats (position, buffer, cache speed) and
send transport commands (pause, seek) while mpv runs backgrounded, so
the app can show its own HUD instead of handing mpv the whole terminal.
"""

from __future__ import annotations

import contextlib
import json
import socket
import time
from collections.abc import Callable
from pathlib import Path


class MpvIPCError(Exception):
    pass


class MpvIPC:
    """One socket connection to a running mpv's IPC server. If a read or
    write fails while mpv's own process is still alive (a brief hang, a
    re-buffer), `get_property`/`command` reconnect once and retry rather
    than surfacing a transient socket error as playback having ended.
    """

    def __init__(self, socket_path: Path, is_alive: Callable[[], bool]) -> None:
        self._socket_path = socket_path
        self._is_alive = is_alive
        self._sock: socket.socket | None = None
        self._recv_buffer = b""
        self._next_request_id = 1

    def connect(self, timeout: float = 5.0) -> None:
        """Connect, retrying briefly -- mpv needs a moment after spawn to
        create the socket file."""
        deadline = time.monotonic() + timeout
        last_exc: OSError | None = None
        while time.monotonic() < deadline:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(1.0)
                sock.connect(str(self._socket_path))
            except OSError as exc:
                last_exc = exc
                sock.close()
                time.sleep(0.1)
                continue
            self._sock = sock
            self._recv_buffer = b""
            return
        raise MpvIPCError(f"could not connect to mpv IPC socket: {last_exc}")

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None

    def get_property(self, name: str) -> object:
        reply = self._request(["get_property", name])
        return reply.get("data")

    def command(self, *args: object) -> None:
        self._request(list(args))

    def _request(self, command: list[object]) -> dict:
        request_id = self._next_request_id
        self._next_request_id += 1
        payload = {"command": command, "request_id": request_id}

        for attempt in range(2):  # one transparent reconnect-and-retry
            try:
                self._send(payload)
                return self._await_reply(request_id)
            except (OSError, ConnectionError) as exc:
                if attempt == 1:
                    raise MpvIPCError(str(exc)) from exc
                self._reconnect()
        raise AssertionError("unreachable")

    def _send(self, payload: dict) -> None:
        if self._sock is None:
            raise ConnectionError("not connected")
        self._sock.sendall((json.dumps(payload) + "\n").encode())

    def _await_reply(self, request_id: int) -> dict:
        while True:
            line = self._read_line()
            reply = json.loads(line)
            if reply.get("request_id") != request_id:
                continue  # an unrelated event notification -- keep reading
            if reply.get("error") != "success":
                raise MpvIPCError(str(reply.get("error")))
            return reply

    def _read_line(self) -> bytes:
        if self._sock is None:
            raise ConnectionError("not connected")
        while b"\n" not in self._recv_buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("mpv IPC socket closed")
            self._recv_buffer += chunk
        line, _, self._recv_buffer = self._recv_buffer.partition(b"\n")
        return line

    def _reconnect(self) -> None:
        if not self._is_alive():
            raise MpvIPCError("mpv process has exited")
        self.close()
        self.connect(timeout=3.0)
