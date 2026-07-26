"""Tests for opening comics through a running viewer process."""

import socket
import time
from pathlib import Path

import cdisplayagain


def test_open_request_server_dispatches_path(tk_root, tmp_path, monkeypatch):
    """Dispatch a Unix socket path through the Tk event loop."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    received: list[Path] = []
    server = cdisplayagain.OpenRequestServer(tk_root, received.append)
    requested_path = tmp_path / "comic.cbz"

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(cdisplayagain.ipc_socket_path()))
    client.sendall(f"{requested_path}\n".encode())
    client.close()

    for _ in range(20):
        tk_root.update()
        if received:
            break
        time.sleep(0.01)

    server.close()

    assert received == [requested_path]
    assert not cdisplayagain.ipc_socket_path().exists()


def test_open_request_server_recovers_stale_socket(tk_root, tmp_path, monkeypatch):
    """Replace a socket left behind by a process that exited without cleanup."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    stale_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale_socket.bind(str(cdisplayagain.ipc_socket_path()))
    stale_socket.close()

    server = cdisplayagain.OpenRequestServer(tk_root, lambda _: None)
    server.close()

    assert not cdisplayagain.ipc_socket_path().exists()
