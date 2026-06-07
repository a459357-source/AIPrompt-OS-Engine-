"""
web_app.py — FastAPI Web UI for the Galgame Runtime
=====================================================
Thin app factory that mounts route modules from ui/routes/.
Previously a 3020-line monolithic file — now delegates to:
  • ui/routes/api.py       — JSON API (game-state, npcs, history, etc.)
  • ui/routes/game.py      — Main game pages (/, /next, save/load, etc.)
  • ui/routes/world.py     — World creation & AI generators
  • ui/routes/npc.py       — NPC management
  • ui/routes/settings.py  — Settings, dashboard, export
  • ui/templates.py        — HTML template constants

Start with: python engine/run.py --mode web
Or directly:  uvicorn ui.web_app:app --reload
"""

from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import config

# Initialize file logging for uvicorn workers
config.setup_logging()

app = FastAPI(
    title="Prompt OS Galgame Runtime",
    description="🎮 Interactive AI Narrative Engine — Web UI",
    version="1.0.0",
)

# Allow CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve local JS libraries for offline dashboard / graph pages
_static_dir = config.OUTPUT_DIR
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ── Mount route modules ────────────────────────────────────────────

from ui.routes.api import router as api_router
from ui.routes.game import router as game_router
from ui.routes.world import router as world_router
from ui.routes.npc import router as npc_router
from ui.routes.settings import router as settings_router

app.include_router(api_router)
app.include_router(game_router)
app.include_router(world_router)
app.include_router(npc_router)
app.include_router(settings_router)


# ── Standalone utility routes (kept at root level for frontend compat) ──

@app.get("/health")
async def health():
    """Lightweight health-check endpoint (polled by frontend JS)."""
    return {"status": "ok", "engine": "Prompt OS Galgame Runtime v1"}


@app.post("/shutdown")
async def shutdown():
    """Gracefully shut down the server."""
    import os
    os._exit(0)
