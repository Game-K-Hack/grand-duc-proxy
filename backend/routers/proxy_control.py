"""
Contrôle du proxy Rust : statut, logs en direct (SSE), redémarrage.

Fonctionne en 3 modes :
- Windows natif  : tasklist / taskkill / Popen
- Linux natif    : pgrep / pkill / Popen
- Docker         : API Docker via le socket Unix (/var/run/docker.sock)
"""

import asyncio
import json
import os
import platform
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config   import settings
from models   import User
from security import require_permission, require_permission_query

router = APIRouter()

LOG_FILE  = Path(settings.PROXY_LOG_FILE)
PROXY_EXE = Path(settings.PROXY_EXE)
WORK_DIR  = Path(settings.PROXY_WORK_DIR)

# Nombre de lignes de l'historique envoyées à la connexion
TAIL_LINES = 300

# ── Détection du mode d'exécution ──────────────────────────────────────────

_IS_WINDOWS = platform.system() == "Windows"
_IN_DOCKER  = os.path.exists("/.dockerenv")

# Nom du conteneur proxy Docker (convention docker-compose : <projet>-proxy-1)
_DOCKER_PROXY_CONTAINER = os.environ.get("PROXY_CONTAINER_NAME", "grand-duc-proxy-1")


# ── Helpers Docker ─────────────────────────────────────────────────────────

def _docker_cmd(*args: str) -> subprocess.CompletedProcess:
    """Exécute une commande docker CLI."""
    return subprocess.run(
        ["docker", *args],
        capture_output=True, text=True, timeout=10,
    )


def _docker_is_running() -> bool:
    r = _docker_cmd("inspect", "-f", "{{.State.Running}}", _DOCKER_PROXY_CONTAINER)
    return r.stdout.strip() == "true"


def _docker_restart():
    _docker_cmd("restart", _DOCKER_PROXY_CONTAINER)


# ── Helpers natifs (Windows / Linux) ───────────────────────────────────────

def _native_is_running() -> bool:
    try:
        if _IS_WINDOWS:
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {PROXY_EXE.name}', '/NH'],
                capture_output=True, text=True,
            )
            return PROXY_EXE.name.lower() in result.stdout.lower()
        else:
            result = subprocess.run(
                ['pgrep', '-f', PROXY_EXE.name],
                capture_output=True, text=True,
            )
            return result.returncode == 0
    except FileNotFoundError:
        return False


def _native_kill():
    try:
        if _IS_WINDOWS:
            subprocess.run(
                ['taskkill', '/F', '/IM', PROXY_EXE.name],
                capture_output=True,
            )
        else:
            subprocess.run(
                ['pkill', '-f', PROXY_EXE.name],
                capture_output=True,
            )
    except FileNotFoundError:
        pass


def _native_spawn():
    kwargs = dict(
        cwd=str(WORK_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if _IS_WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    subprocess.Popen([str(PROXY_EXE)], **kwargs)


# ── Interface unifiée ──────────────────────────────────────────────────────

def _is_running() -> bool:
    if _IN_DOCKER:
        try:
            return _docker_is_running()
        except Exception:
            return False
    return _native_is_running()


def _restart_proxy():
    """Redémarre le proxy (Docker: restart conteneur, natif: kill+spawn)."""
    if _IN_DOCKER:
        _docker_restart()
    else:
        _native_kill()


def _spawn_if_native():
    """Lance le proxy en mode natif uniquement (no-op en Docker)."""
    if not _IN_DOCKER:
        _native_spawn()


# ── SSE log stream ─────────────────────────────────────────────────────────

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
async def get_status(_user: User = Depends(require_permission("proxy_logs.read"))):
    return StatusOut(running=_is_running(), log_exists=LOG_FILE.exists())


@router.get("/logs")
async def stream_logs(_user: User = Depends(require_permission_query("proxy_logs.read"))):
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
async def restart_proxy(_user: User = Depends(require_permission("proxy.restart"))):
    """Redémarre le proxy (conteneur Docker ou processus natif)."""
    was_running = _is_running()

    if _IN_DOCKER:
        _docker_restart()
        await asyncio.sleep(2)
    else:
        if was_running:
            _native_kill()
            await asyncio.sleep(0.8)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _native_spawn()
        await asyncio.sleep(0.5)

    from services.email import notify
    asyncio.create_task(notify(
        "proxy_restart",
        "Proxy redémarré",
        [f"Par : {_user.username}", f"Était en cours : {'oui' if was_running else 'non'}"],
    ))

    return {"restarted": True, "was_running": was_running, "now_running": _is_running()}
