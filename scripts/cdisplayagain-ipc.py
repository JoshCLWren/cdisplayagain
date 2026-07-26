#!/usr/bin/env python3
"""Send a comic path to an already-running cdisplayagain process."""

from __future__ import annotations

import socket
import sys


def main() -> int:
    """Send one path to the Unix socket supplied on the command line."""
    if len(sys.argv) != 3:
        return 2
    socket_path, comic_path = sys.argv[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1.0)
            connection.connect(socket_path)
            connection.sendall(f"{comic_path}\n".encode())
    except OSError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
