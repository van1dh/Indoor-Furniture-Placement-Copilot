"""HTTP API for the layout engine.

Run it with ``uvicorn app:app --port 5000`` from this folder. Set STATIC_DIR to a built frontend (``dist``) to
serve the app from the same origin, as the Docker image does.
"""
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from layout import InputError, PlacementError, describe, evaluate_layout, generate_layout, refine_layout

MAX_BODY_BYTES = 100_000
CLIENT_ORIGINS = os.environ.get("CLIENT_ORIGIN", "http://localhost:3000").split(",")
STATIC_DIR = os.environ.get("STATIC_DIR")

log = logging.getLogger("layout.api")

app = FastAPI(title="Indoor Furniture Placement Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CLIENT_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


@app.exception_handler(ApiError)
async def api_error(request, exc):
    return JSONResponse({"error": exc.message}, status_code=exc.status)


async def read_object(request, fields):
    """The JSON object in the request body, keeping only ``fields``."""
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise ApiError(413, "Request body is too large")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(400, "Request body is not valid JSON")
    if not isinstance(payload, dict):
        raise ApiError(400, "Request body must be a JSON object")
    return {k: payload[k] for k in fields if k in payload}


async def run(action, payload):
    # Layout search is CPU-bound and the copilot blocks on the Claude API, so keep both off the event loop
    try:
        return await run_in_threadpool(action, payload)
    except (InputError, PlacementError) as e:  # both are the client's to fix
        raise ApiError(400, str(e))
    except Exception:
        log.exception("%s failed", action.__name__)
        raise ApiError(500, "Layout generation failed")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/options")
def options():
    """Furniture types, presets, limits and form defaults."""
    return describe()


@app.post("/api/generate")
async def generate(request: Request):
    payload = await read_object(request, ("preset", "room", "furniture", "notes", "seed", "preferences"))
    return await run(generate_layout, payload)


@app.post("/api/refine")
async def refine(request: Request):
    """Change an existing layout as a chat message asks ("move the bed under the window")."""
    payload = await read_object(request, ("request", "layout", "message", "history"))
    return await run(refine_layout, payload)


@app.post("/api/evaluate")
async def evaluate(request: Request):
    """Score a layout the user arranged by hand."""
    payload = await read_object(request, ("request", "layout"))
    return await run(evaluate_layout, payload)


if STATIC_DIR:
    static_root = Path(STATIC_DIR).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        # Serve built files, and index.html for client-side routes such as /result
        if path.startswith("api/"):
            raise ApiError(404, "Not found")
        file = (static_root / path).resolve()
        if path and file.is_file() and file.is_relative_to(static_root):
            return FileResponse(file)
        return FileResponse(static_root / "index.html")
