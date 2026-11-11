import argparse
import os
import secrets
import socket
import sys
import threading
import time

import uvicorn

from backend.config import HOST, PORT

# First stdout line in sidecar mode; the Tauri shell parses it to find the API.
READY_PREFIX = "FINANCE_BACKEND_READY"


def wait_for_server(server: uvicorn.Server, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return
        time.sleep(0.05)
    raise RuntimeError("Backend failed to start")


def run_sidecar() -> None:
    """Run under the Tauri shell: random port, per-launch token, exit with parent."""
    token = secrets.token_urlsafe(32)
    os.environ["FINANCE_API_TOKEN"] = token

    from backend.api import app

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))
    port = sock.getsockname()[1]

    log_level = os.environ.get("FINANCE_LOG_LEVEL", "warning")
    server = uvicorn.Server(uvicorn.Config(app, log_level=log_level))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    wait_for_server(server)

    print(f"{READY_PREFIX} {port} {token}", flush=True)

    # The shell holds our stdin open; EOF means it exited (or crashed), so stop too.
    while sys.stdin.read(4096):
        pass
    server.should_exit = True
    thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(prog="python -m backend")
    parser.add_argument(
        "--sidecar", action="store_true", help="run as the Tauri app's backend process"
    )
    args = parser.parse_args()

    if args.sidecar:
        run_sidecar()
    else:
        # Dev mode: fixed port, reached through the Vite proxy in a browser.
        uvicorn.run("backend.api:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
