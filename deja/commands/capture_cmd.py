"""``deja capture`` — Scene 3 fallback: write BEFORE and AFTER PNGs.

Rehearsal insurance so the headline beat survives a flaky live render (spec §7).
Uses Playwright to screenshot the ``deja ui`` view, so the browser output IS
what the judges saw a moment ago — same layout, same styling.

Requires the ``capture`` extra: ``pip install -e '.[capture]'``.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from deja.commands.memify_cmd import run_memify


CAPTURE_DIR = Path("captures")


def capture_before_and_after(host: str = "127.0.0.1", port: int = 8765) -> tuple[Path, Path]:
    """Serve the UI, screenshot BEFORE, run memify live, screenshot AFTER.

    Returns the two file paths. Not idempotent — always writes fresh PNGs.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - guidance path
        raise SystemExit(
            "Playwright is not installed. Run: pip install -e '.[capture]' "
            "then `playwright install chromium`."
        ) from exc

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    before = CAPTURE_DIR / "graph_before.png"
    after = CAPTURE_DIR / "graph_after.png"

    with _uvicorn(host, port):
        _wait_for_server(host, port)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(f"http://{host}:{port}/")
            page.wait_for_selector("#graph")
            # give the physics engine a moment to settle
            page.wait_for_timeout(3000)
            page.screenshot(path=str(before), full_page=True)

            # Run memify against the live graph, then let the UI poll for it.
            asyncio.run(run_memify())
            page.wait_for_timeout(3500)  # 2s poll interval + flash animation
            page.screenshot(path=str(after), full_page=True)
            browser.close()

    return before, after


@contextmanager
def _uvicorn(host: str, port: int) -> Iterator[subprocess.Popen]:
    """Run a temporary uvicorn subprocess serving the graph UI."""
    proc = subprocess.Popen(
        [
            "uvicorn",
            "deja.ui.server:create_app",
            "--factory",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]
    )
    try:
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> None:
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.2)
    raise TimeoutError(f"UI server did not come up on {host}:{port}")
