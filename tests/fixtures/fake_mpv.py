"""Stand-in for mpv in tests: speaks just enough of the JSON-IPC protocol
for PlaybackHudScreen's polling loop, and exits cleanly on SIGTERM (as a
real mpv does) instead of a real video/audio pipeline.
"""

from __future__ import annotations

import json
import signal
import socket
import sys

_VALUES = {
    "pause": False,
    "time-pos": 12.5,
    "duration": 100.0,
    "demuxer-cache-duration": 8.0,
    "cache-speed": 512000,
}


def main() -> None:
    ipc_path = next(
        arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--input-ipc-server=")
    )

    running = True

    def handle_term(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_term)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(ipc_path)
    server.listen(1)
    server.settimeout(0.2)

    conn: socket.socket | None = None
    while running:
        if conn is None:
            try:
                conn, _ = server.accept()
                conn.settimeout(0.2)
            except TimeoutError:
                continue
        try:
            chunk = conn.recv(4096)
        except TimeoutError:
            continue
        except OSError:
            conn = None
            continue
        if not chunk:
            conn = None
            continue
        for line in chunk.splitlines():
            if not line.strip():
                continue
            request = json.loads(line)
            command = request["command"]
            prop = command[1] if command[0] == "get_property" else None
            reply = {
                "request_id": request["request_id"],
                "error": "success",
                "data": _VALUES.get(prop),
            }
            conn.sendall((json.dumps(reply) + "\n").encode())

    sys.exit(0)


if __name__ == "__main__":
    main()
