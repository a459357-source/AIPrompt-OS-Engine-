"""
web_app.py — FastAPI Web UI for the Galgame Runtime
=====================================================
React SPA is the primary UI. Backend also exposes save/load/export utilities.
"""

from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

import config

config.setup_logging()
config.ensure_runtime_files()

app = FastAPI(
    title="Prompt OS Galgame Runtime",
    description="🎮 Interactive AI Narrative Engine — Web UI",
    version=config.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = config.OUTPUT_DIR
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# React client routes — explicit GET handlers before SPA fallback
REACT_CLIENT_ROUTES = ("new", "game", "npcs", "dashboard", "visual", "settings")


async def _serve_react_spa(request: Request):
    """Serve bundled SPA or redirect dev traffic to the Vite server."""
    if config.has_bundled_frontend():
        return FileResponse(config.FRONTEND_DIST / "index.html")
    return RedirectResponse(url=config.frontend_url(request.url.path), status_code=302)


for _route in REACT_CLIENT_ROUTES:
    app.add_api_route(f"/{_route}", _serve_react_spa, methods=["GET"])


@app.get("/health")
async def health():
    """Lightweight health-check endpoint (polled by frontend JS)."""
    return {"status": "ok", "engine": f"Prompt OS Galgame Runtime v{config.APP_VERSION}"}


@app.post("/shutdown")
async def shutdown(token: str = ""):
    """Gracefully shut down the server."""
    import sys
    sys.exit(0)


from ui.routes.api import router as api_router
from ui.routes.game import router as game_router
from ui.routes.world import router as world_router
from ui.routes.settings import router as settings_router
from ui.routes.visual import router as visual_router
from ui.routes.narrative import router as narrative_router

app.include_router(api_router)
app.include_router(game_router)
app.include_router(world_router)
app.include_router(settings_router)
app.include_router(visual_router)
app.include_router(narrative_router)


_SPA_EXCLUDE_PREFIXES = ("api/", "static/", "generate-")
_SPA_EXCLUDE_EXACT = frozenset({
    "health", "export", "save", "load", "saves", "reset", "shutdown",
})


@app.get("/{full_path:path}")
async def serve_spa_fallback(full_path: str):
    """SPA fallback: bundled dist, or dev redirect to Vite for nested client routes."""
    if full_path.startswith(_SPA_EXCLUDE_PREFIXES) or full_path in _SPA_EXCLUDE_EXACT:
        raise HTTPException(404)

    first_segment = full_path.split("/", 1)[0] if full_path else ""

    if config.has_bundled_frontend():
        fp = config.FRONTEND_DIST / full_path
        if full_path and fp.is_file():
            return FileResponse(fp)
        if first_segment in REACT_CLIENT_ROUTES or not full_path:
            return FileResponse(config.FRONTEND_DIST / "index.html")
        raise HTTPException(404)

    if first_segment in REACT_CLIENT_ROUTES:
        return RedirectResponse(url=config.frontend_url(f"/{full_path}"), status_code=302)
    raise HTTPException(404)
