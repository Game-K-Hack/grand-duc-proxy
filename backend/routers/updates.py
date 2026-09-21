import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models   import AppSetting, User
from security import require_permission
from version  import VERSION
from services import docker_cli, github, updater

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class ModuleOut(BaseModel):
    service:    str
    label:      str
    container:  Optional[str] = None
    image:      Optional[str] = None
    tag:        Optional[str] = None
    version:    Optional[str] = None
    revision:   Optional[str] = None
    running:    bool = False
    started_at: Optional[str] = None
    managed:    bool = False
    kind:       str                      # ghcr | external | local-build | native | absent
    status:     str                      # up_to_date | outdated | ahead | unknown | unmanaged


class LatestOut(BaseModel):
    tag:          Optional[str] = None
    html_url:     Optional[str] = None
    published_at: Optional[str] = None
    notes:        Optional[str] = None
    assets:       list[dict] = []
    checked_at:   Optional[str] = None
    stale:        bool = False
    rate_limited: bool = False
    rate_reset:   Optional[int] = None
    error:        Optional[str] = None


class ProgressOut(BaseModel):
    state:        str                    # idle | running | success | failed
    target:       Optional[str] = None
    requested_by: Optional[str] = None
    exit_code:    Optional[int] = None
    started_at:   Optional[str] = None
    finished_at:  Optional[str] = None
    steps:        list[str] = []
    log:          list[str] = []


class UpdateStatusOut(BaseModel):
    mode:             str               # docker | native
    can_update:       bool
    reason:           Optional[str] = None
    project:          Optional[str] = None
    current_version:  Optional[str] = None
    modules:          list[ModuleOut]
    latest:           LatestOut
    update_available: bool
    updater:          ProgressOut


class ApplyIn(BaseModel):
    refresh_compose: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _proxy_runtime(db: AsyncSession) -> dict:
    """Version publiée par le proxy lui-même (cf. proxy/src/main.rs)."""
    row = await db.get(AppSetting, "proxy_runtime")
    if not row:
        return {}
    try:
        return json.loads(row.value) or {}
    except ValueError:
        return {}


def _module_status(version: Optional[str], latest_tag: Optional[str], managed: bool) -> str:
    if not managed:
        return "unmanaged"
    return github.compare(version, latest_tag)


async def _collect(db: AsyncSession) -> UpdateStatusOut:
    latest_raw = await github.get_latest(db)
    latest = LatestOut(
        tag=latest_raw.get("tag"),
        html_url=latest_raw.get("html_url") or github.RELEASES_URL,
        published_at=latest_raw.get("published_at"),
        notes=latest_raw.get("notes"),
        assets=latest_raw.get("assets") or [],
        checked_at=latest_raw.get("checked_at"),
        stale=github.is_stale(latest_raw),
        rate_limited=bool(latest_raw.get("rate_limited")),
        rate_reset=latest_raw.get("rate_reset"),
        error=latest_raw.get("error"),
    )
    latest_tag = latest.tag
    runtime = await _proxy_runtime(db)
    modules: list[ModuleOut] = []

    # ── Mode natif : pas de Docker, lecture seule ────────────────────────────
    if not docker_cli.is_available():
        modules.append(ModuleOut(
            service="backend", label=docker_cli.SERVICE_LABELS["backend"],
            version=VERSION, running=True, kind="native",
            status=github.compare(VERSION, latest_tag),
        ))
        if runtime.get("version"):
            modules.append(ModuleOut(
                service="proxy", label=docker_cli.SERVICE_LABELS["proxy"],
                version=runtime["version"], running=True, kind="native",
                started_at=runtime.get("started_at"),
                status=github.compare(runtime["version"], latest_tag),
            ))
        return UpdateStatusOut(
            mode="native", can_update=False,
            reason="Installation sans Docker : la mise à jour automatique n'est pas "
                   "disponible. Téléchargez le bundle de la release et remplacez les fichiers.",
            current_version=VERSION, modules=modules, latest=latest,
            update_available=github.compare(VERSION, latest_tag) == "outdated",
            updater=ProgressOut(state="idle"),
        )

    # ── Mode Docker ──────────────────────────────────────────────────────────
    info = docker_cli.project_info()
    project = info.get("project")
    if not project:
        return UpdateStatusOut(
            mode="docker", can_update=False,
            reason="Projet Docker Compose non détecté : ce conteneur n'a pas été "
                   "lancé par Docker Compose.",
            current_version=VERSION, modules=[], latest=latest,
            update_available=False, updater=ProgressOut(state="idle"),
        )

    described = [docker_cli.describe_container(c) for c in docker_cli.project_containers(project)]
    described = [d for d in described if d.get("service")]
    described.sort(key=lambda d: list(docker_cli.SERVICE_LABELS).index(d["service"])
                   if d["service"] in docker_cli.SERVICE_LABELS else 99)

    current_version = None
    for d in described:
        version = d["version"]
        # Le proxy en network_mode host publie sa version en base : c'est plus
        # fiable que le label quand la stack a été construite localement.
        if d["service"] == "proxy" and not version:
            version = runtime.get("version")
        if d["service"] == "backend":
            current_version = version or VERSION
        modules.append(ModuleOut(
            label=docker_cli.SERVICE_LABELS.get(d["service"], d["service"]),
            status=_module_status(version, latest_tag, d["managed"]),
            **{**d, "version": version},
        ))

    # Proxy natif alors que la stack est en Docker : il n'a pas de conteneur.
    if runtime.get("version") and not any(m.service == "proxy" for m in modules):
        modules.append(ModuleOut(
            service="proxy", label=docker_cli.SERVICE_LABELS["proxy"],
            version=runtime["version"], running=True, kind="native",
            started_at=runtime.get("started_at"),
            status="unmanaged",
        ))

    managed = [m for m in modules if m.managed]
    if not managed:
        can_update, reason = False, (
            "Stack de développement : les images sont construites localement "
            "(docker compose build) et non téléchargées depuis le registre."
        )
    elif not latest_tag:
        can_update, reason = False, "Aucune version publiée n'a pu être récupérée depuis GitHub."
    else:
        can_update, reason = True, None

    update_available = bool(
        can_update and any(m.status == "outdated" for m in managed)
    )

    return UpdateStatusOut(
        mode="docker", can_update=can_update, reason=reason, project=project,
        current_version=current_version or VERSION, modules=modules, latest=latest,
        update_available=update_available, updater=ProgressOut(**updater.progress()),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=UpdateStatusOut)
async def get_status(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("updates.read")),
):
    """Versions déployées, dernière version publiée, et état de l'updater."""
    return await _collect(db)


@router.post("/check", response_model=UpdateStatusOut)
async def check_now(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("updates.read")),
):
    """Force la vérification GitHub (garde anti-martèlement de 60 s côté service)."""
    await github.get_latest(db, force=True)
    return await _collect(db)


@router.get("/progress", response_model=ProgressOut)
async def get_progress(
    _user: User = Depends(require_permission("updates.read")),
):
    """État de la mise à jour, y compris après recréation du backend."""
    if not docker_cli.is_available():
        return ProgressOut(state="idle")
    return ProgressOut(**updater.progress())


@router.post("/apply", status_code=202)
async def apply_update(
    body:  ApplyIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("updates.apply")),
):
    """Lance la mise à jour vers la dernière version publiée.

    Répond 202 puis rend la main : l'updater tourne dans un conteneur séparé et
    va recréer ce backend. Le résultat se lit ensuite via `/progress`.
    """
    status = await _collect(db)

    if status.mode != "docker":
        raise HTTPException(400, "Mise à jour automatique indisponible en mode natif.")
    if not status.can_update and not updater.FORCE:
        raise HTTPException(400, status.reason or "Mise à jour impossible sur cette installation.")

    target = status.latest.tag
    if not target or not updater.valid_version(target):
        raise HTTPException(400, f"Version cible invalide : {target!r}")

    if status.updater.state == "running":
        raise HTTPException(409, "Une mise à jour est déjà en cours.")

    info = docker_cli.project_info()
    working_dir = info.get("working_dir")
    if not updater.valid_working_dir(working_dir):
        raise HTTPException(400, "Répertoire du projet introuvable ou invalide.")
    if updater.is_windows_host_path(working_dir):
        raise HTTPException(400,
            "Mise à jour automatique indisponible sous Docker Desktop Windows : le "
            "répertoire du projet est un chemin Windows, qu'un conteneur Linux ne peut "
            "pas monter. Ce mode est destiné au développement ; en production (Linux) "
            "la mise à jour fonctionne normalement.")

    ok, err = updater.ensure_image()
    if not ok:
        raise HTTPException(400, f"Image de mise à jour indisponible : {err}")

    # Piste d'audit, et source de la notification au redémarrage : le backend
    # actuel ne sera plus là pour l'émettre.
    from_version = status.current_version
    row = await db.get(AppSetting, "update_request")
    payload = json.dumps({
        "target": target,
        "from_version": from_version,
        "requested_by": _user.username,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    })
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key="update_request", value=payload))
    await db.commit()

    with_proxy = any(m.service == "proxy" and m.kind != "native" for m in status.modules)
    ok, err = updater.launch(
        target=target,
        project=status.project,
        working_dir=working_dir,
        config_files=info.get("config_files") or [],
        with_proxy_profile=with_proxy,
        refresh_compose=body.refresh_compose,
        requested_by=_user.username,
    )
    if not ok:
        raise HTTPException(500, f"Lancement de la mise à jour échoué : {err}")

    return {"started": True, "target": target, "from_version": from_version}
