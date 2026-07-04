"""FastAPI app that serves the live graph view.

Kept small: one JSON endpoint + one HTML template. Everything else (styling,
force layout, polling) is client-side in ``static/index.html``.
"""

from __future__ import annotations

from pathlib import Path

import json

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from deja.config import load_settings


HERE = Path(__file__).resolve().parent
INDEX = HERE / "static" / "index.html"


def create_app() -> FastAPI:
    settings = load_settings()
    snapshot_path = settings.snapshot_path

    app = FastAPI(title="deja graph viewer")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(INDEX)

    @app.get("/api/graph")
    async def api_graph() -> JSONResponse:
        # Read the snapshot file that mutation commands (seed/chat/memify/forget)
        # write on completion. Avoids competing with the CLI for Ladybug's
        # single-writer lock — see graph_store.export_snapshot_to_file for why.
        if not snapshot_path.exists():
            return JSONResponse(
                {
                    "nodes": [],
                    "edges": [],
                    "note": "no snapshot yet — run `deja seed`",
                }
            )
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        return JSONResponse(payload)

    return app
