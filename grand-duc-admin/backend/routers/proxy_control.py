"""
Contrôle du proxy Rust : statut, logs en direct (SSE), redémarrage.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config   import settings
from database import get_db
from models   import User
from security import get_current_user, get_current_user_query, require_admin

router = APIRouter()

LOG_FILE  = Path(settings.PROXY_LOG_FILE)
PROXY_EXE = Path(settings.PROXY_EXE)
WORK_DIR  = Path(settings.PROXY_WORK_DIR)

# Nombre de lignes de l'historique envoyées à la connexion
TAIL_LINES = 300


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_running() -> bool:
    """Vérifie si le processus proxy est en cours d'exécution (Windows)."""
    result = subprocess.run(
        ['tasklist', '/FI', f'IMAGENAME eq {PROXY_EXE.name}', '/NH'],
        capture_output=True, text=True,
    )
    return PROXY_EXE.name.lower() in result.stdout.lower()


def _kill_proxy():
    subprocess.run(
        ['taskkill', '/F', '/IM', PROXY_EXE.name],
        capture_output=True,
    )


def _spawn_proxy():
    # stdout/stderr → DEVNULL : le proxy écrit lui-même dans grand-duc.log via le file layer.
    # Rediriger stdout ici causerait des doublons avec ANSI dans le fichier.
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [str(PROXY_EXE)],
        cwd=str(WORK_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )


async def _log_stream():
    """Générateur SSE : envoie les N dernières lignes puis streame les nouvelles."""
    # Historique
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in lines[-TAIL_LINES:]:
            payload = json.dumps({"line": line.rstrip()})
            yield f"data: {payload}\n\n"

    # Stream live
    with open(LOG_FILE, 'a+', encoding='utf-8', errors='replace') as f:
        f.seek(0, 2)  # aller à la fin
        while True:
            line = f.readline()
            if line:
                payload = json.dumps({"line": line.rstrip()})
                yield f"data: {payload}\n\n"
            else:
                await asyncio.sleep(0.25)


# ── Endpoints ─────────────────────────────────────────────────────────────────

class StatusOut(BaseModel):
    running: bool
    log_exists: bool


@router.get("/status", response_model=StatusOut)
async def get_status(_user: User = Depends(get_current_user)):
    return StatusOut(running=_is_running(), log_exists=LOG_FILE.exists())


@router.get("/logs")
async def stream_logs(_user: User = Depends(get_current_user_query)):
    """SSE — streame les logs du proxy (token via query param pour EventSource)."""
    if not LOG_FILE.exists():
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch()
    return StreamingResponse(
        _log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/restart")
async def restart_proxy(_user: User = Depends(require_admin)):
    """Tue le processus proxy existant et en démarre un nouveau."""
    was_running = _is_running()
    if was_running:
        _kill_proxy()
        await asyncio.sleep(0.8)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _spawn_proxy()
    await asyncio.sleep(0.5)

    return {"restarted": True, "was_running": was_running, "now_running": _is_running()}
