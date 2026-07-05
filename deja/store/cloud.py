"""Optional Cognee Cloud connection — routes the same operations to the hosted
service instead of the local embedded stack.

Enabled per-command via ``--cloud``. Reads ``COGNEE_SERVICE_URL`` and
``COGNEE_API_KEY`` (get them from https://platform.cognee.ai → API Keys; the
free tier needs no card). After a successful ``cognee.serve(...)`` the top-level
Cognee SDK operations route to the remote instance.

Best-effort: never raises. If the installed cognee has no ``serve`` or the
connect fails, we return a reason and the caller falls back to local — the demo
is never blocked. The exact ``serve()`` signature is version-specific; run
``spike_cognee.py`` / ``help(cognee.serve)`` to confirm and tighten here.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def connect_cloud() -> tuple[bool, str]:
    """Connect the Cognee SDK to Cognee Cloud. Returns (connected, message)."""
    try:
        import cognee
    except ImportError as exc:
        return False, f"cognee not installed: {exc}"

    serve = getattr(cognee, "serve", None)
    if serve is None:
        return False, "this cognee version has no `serve()` — upgrade to use Cognee Cloud"

    url = os.getenv("COGNEE_SERVICE_URL")
    api_key = os.getenv("COGNEE_API_KEY")
    if not api_key:
        return False, "COGNEE_API_KEY not set (get one at https://platform.cognee.ai)"

    try:
        # Prefer explicit args; fall back to env-var-driven serve() if the
        # signature differs across versions.
        try:
            await serve(url=url, api_key=api_key)
        except TypeError:
            await serve()
        target = url or "Cognee Cloud (default endpoint)"
        return True, f"connected to {target}"
    except Exception as exc:  # noqa: BLE001 — best-effort, fall back to local
        logger.warning("Cognee Cloud connect failed: %s", exc)
        return False, f"cloud connect failed: {type(exc).__name__}: {exc}"
