"""
Intégrations RMM : CRUD + synchronisation des agents vers client_users.
Supporte : Tactical RMM, NinjaRMM, Datto RMM, Atera.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, AsyncSessionLocal
from models import ClientUser, RmmIntegration
from security import require_permission
from models import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Données d'agent normalisées ────────────────────────────────────────────────

@dataclass
class AgentData:
    agent_id: str
    ip:       str
    hostname: str
    os:       str


# ── Adaptateurs RMM ────────────────────────────────────────────────────────────

async def _fetch_tactical(intg: RmmIntegration) -> list[AgentData]:
    """Tactical RMM — API REST avec header X-API-KEY."""
    headers = {"X-API-KEY": intg.api_key}
    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        r = await client.get(f"{intg.url.rstrip('/')}/api/agents/", headers=headers)
        r.raise_for_status()
        agents = r.json()

    results = []
    for a in agents:
        # local_ips est une liste séparée par virgules ou un tableau
        raw_ips = a.get("local_ips", "") or ""
        if isinstance(raw_ips, list):
            ips = [ip.strip() for ip in raw_ips if ip.strip()]
        else:
            ips = [ip.strip() for ip in str(raw_ips).split(",") if ip.strip()]
        # on prend la première IP non-loopback
        ip = next((i for i in ips if not i.startswith("127.")), ips[0] if ips else None)
        if not ip:
            continue
        results.append(AgentData(
            agent_id=str(a.get("agent_id") or a.get("pk") or a.get("id", "")),
            ip=ip,
            hostname=a.get("hostname", ""),
            os=a.get("operating_system", ""),
        ))
    return results


async def _fetch_ninja(intg: RmmIntegration) -> list[AgentData]:
    """NinjaRMM — OAuth2 client_credentials puis GET /v2/devices."""
    base = intg.url.rstrip("/")
    # 1. Récupérer le token OAuth2
    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        token_r = await client.post(
            f"{base}/ws/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": intg.api_key,
                "client_secret": intg.api_secret or "",
                "scope": "monitoring",
            },
        )
        token_r.raise_for_status()
        token = token_r.json()["access_token"]

        # 2. Récupérer les appareils
        r = await client.get(
            f"{base}/v2/devices",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        devices = r.json()

    results = []
    for d in devices:
        ip = d.get("lastIp") or d.get("ipAddress") or ""
        if not ip:
            continue
        results.append(AgentData(
            agent_id=str(d.get("id", "")),
            ip=ip,
            hostname=d.get("systemName") or d.get("dnsName", ""),
            os=(d.get("os") or {}).get("name", ""),
        ))
    return results


async def _fetch_datto(intg: RmmIntegration) -> list[AgentData]:
    """Datto RMM — API v2 avec Basic auth (api_key:api_secret)."""
    base = intg.url.rstrip("/")
    auth = (intg.api_key, intg.api_secret or "")
    async with httpx.AsyncClient(verify=False, timeout=30, auth=auth) as client:
        # Lister tous les sites d'abord
        sites_r = await client.get(f"{base}/api/v2/account/sites")
        sites_r.raise_for_status()
        sites = sites_r.json().get("sites", [])

        results = []
        for site in sites:
            site_uid = site.get("uid") or site.get("id")
            if not site_uid:
                continue
            dev_r = await client.get(f"{base}/api/v2/site/{site_uid}/devices")
            dev_r.raise_for_status()
            devices = dev_r.json().get("devices", [])
            for d in devices:
                ip = (d.get("lastSeenIp") or d.get("intIpAddress") or "").strip()
                if not ip:
                    continue
                results.append(AgentData(
                    agent_id=str(d.get("uid") or d.get("id", "")),
                    ip=ip,
                    hostname=d.get("hostname", ""),
                    os=d.get("operatingSystem", ""),
                ))
    return results


async def _fetch_atera(intg: RmmIntegration) -> list[AgentData]:
    """Atera — API REST avec header X-API-KEY, pagination offset."""
    base = intg.url.rstrip("/")
    headers = {"X-API-KEY": intg.api_key, "Accept": "application/json"}
    results = []
    page = 1
    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        while True:
            r = await client.get(
                f"{base}/api/v3/agents",
                headers=headers,
                params={"page": page, "itemsInPage": 100},
            )
            r.raise_for_status()
            data = r.json()
            agents = data.get("items") or data if isinstance(data, list) else []
            if not agents:
                break
            for a in agents:
                # IpAddresses peut être "192.168.1.10, 10.0.0.5"
                raw = a.get("IpAddresses") or a.get("ipAddresses") or ""
                ips = [i.strip() for i in str(raw).split(",") if i.strip()]
                ip = next((i for i in ips if not i.startswith("127.")), ips[0] if ips else None)
                if not ip:
                    continue
                results.append(AgentData(
                    agent_id=str(a.get("AgentID") or a.get("agentId", "")),
                    ip=ip,
                    hostname=a.get("MachineName") or a.get("ComputerName", ""),
                    os=a.get("OS") or a.get("OperatingSystem", ""),
                ))
            if len(agents) < 100:
                break
            page += 1
    return results


ADAPTERS = {
    "tactical":    _fetch_tactical,
    "ninja":       _fetch_ninja,
    "datto":       _fetch_datto,
    "atera":       _fetch_atera,
}


# ── Logique de synchronisation ─────────────────────────────────────────────────

async def run_sync(integration_id: int) -> dict:
    """Exécute la synchronisation d'une intégration. Retourne un résumé."""
    async with AsyncSessionLocal() as db:
        intg = (await db.execute(
            select(RmmIntegration).where(RmmIntegration.id == integration_id)
        )).scalar_one_or_none()
        if not intg or not intg.enabled:
            return {"error": "Intégration introuvable ou désactivée"}

        adapter = ADAPTERS.get(intg.type)
        if not adapter:
            return {"error": f"Type inconnu : {intg.type}"}

        try:
            agents = await adapter(intg)
        except Exception as exc:
            status = f"Erreur : {exc}"
            await db.execute(
                update(RmmIntegration)
                .where(RmmIntegration.id == integration_id)
                .values(last_sync_at=datetime.now(timezone.utc), last_sync_status=status)
            )
            await db.commit()
            from services.email import notify
            asyncio.create_task(notify(
                "rmm_sync_error",
                f"Erreur de synchronisation RMM : {intg.name}",
                [f"Intégration : <strong>{intg.name}</strong> ({intg.type})", f"Erreur : {exc}"],
            ))
            return {"error": status}

        now = datetime.now(timezone.utc)
        created = updated = skipped = 0

        for agent in agents:
            existing = (await db.execute(
                select(ClientUser).where(ClientUser.ip_address == agent.ip)
            )).scalar_one_or_none()

            if existing:
                if existing.source == "manual":
                    # Ne pas écraser les entrées manuelles, mais mettre à jour last_seen
                    existing.last_seen_rmm = now
                    skipped += 1
                else:
                    # Mettre à jour l'entrée RMM
                    existing.hostname = agent.hostname
                    existing.os = agent.os
                    existing.rmm_agent_id = agent.agent_id
                    existing.last_seen_rmm = now
                    existing.rmm_integration_id = integration_id
                    if not existing.label:
                        existing.label = agent.hostname
                    updated += 1
            else:
                db.add(ClientUser(
                    ip_address=agent.ip,
                    label=agent.hostname,
                    hostname=agent.hostname,
                    os=agent.os,
                    source="rmm",
                    rmm_agent_id=agent.agent_id,
                    last_seen_rmm=now,
                    rmm_integration_id=integration_id,
                ))
                created += 1

        status_msg = f"OK — {created} créés, {updated} mis à jour, {skipped} ignorés (manual)"
        await db.execute(
            update(RmmIntegration)
            .where(RmmIntegration.id == integration_id)
            .values(last_sync_at=now, last_sync_status=status_msg)
        )
        await db.commit()
        return {"created": created, "updated": updated, "skipped": skipped}


# ── Boucle de synchronisation automatique ─────────────────────────────────────

_sync_task: asyncio.Task | None = None


async def _sync_loop():
    """Tâche de fond : synchronise les intégrations selon leur intervalle."""
    while True:
        try:
            await asyncio.sleep(60)  # vérification toutes les minutes
            async with AsyncSessionLocal() as db:
                intgs = (await db.execute(
                    select(RmmIntegration).where(RmmIntegration.enabled == True)
                )).scalars().all()

            now = datetime.now(timezone.utc)
            for intg in intgs:
                if intg.last_sync_at is None:
                    due = True
                else:
                    elapsed = (now - intg.last_sync_at).total_seconds() / 60
                    due = elapsed >= intg.sync_interval_minutes

                if due:
                    logger.info("Sync RMM automatique : %s (%s)", intg.name, intg.type)
                    asyncio.create_task(run_sync(intg.id))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Erreur boucle sync RMM : %s", exc)


def start_sync_loop():
    global _sync_task
    _sync_task = asyncio.create_task(_sync_loop())


def stop_sync_loop():
    if _sync_task:
        _sync_task.cancel()


# ── Schémas Pydantic ───────────────────────────────────────────────────────────

class IntegrationIn(BaseModel):
    name:                  str
    type:                  str
    url:                   str
    api_key:               str
    api_secret:            Optional[str] = None
    enabled:               bool = True
    sync_interval_minutes: int  = 60


class IntegrationUpdate(BaseModel):
    name:                  Optional[str]  = None
    url:                   Optional[str]  = None
    api_key:               Optional[str]  = None
    api_secret:            Optional[str]  = None
    enabled:               Optional[bool] = None
    sync_interval_minutes: Optional[int]  = None


class IntegrationOut(BaseModel):
    id:                    int
    name:                  str
    type:                  str
    url:                   str
    api_key:               str
    api_secret:            Optional[str]
    enabled:               bool
    sync_interval_minutes: int
    last_sync_at:          Optional[str]
    last_sync_status:      Optional[str]
    created_at:            str


def _out(i: RmmIntegration) -> IntegrationOut:
    return IntegrationOut(
        id=i.id, name=i.name, type=i.type, url=i.url,
        api_key=i.api_key, api_secret=i.api_secret,
        enabled=i.enabled, sync_interval_minutes=i.sync_interval_minutes,
        last_sync_at=i.last_sync_at.isoformat() if i.last_sync_at else None,
        last_sync_status=i.last_sync_status,
        created_at=i.created_at.isoformat(),
    )


# ── Endpoints CRUD ─────────────────────────────────────────────────────────────

VALID_TYPES = set(ADAPTERS.keys())


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.rmm.read")),
):
    rows = (await db.execute(select(RmmIntegration).order_by(RmmIntegration.name))).scalars().all()
    return [_out(r) for r in rows]


@router.post("", response_model=IntegrationOut, status_code=201)
async def create_integration(
    body:  IntegrationIn,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.rmm.write")),
):
    if body.type not in VALID_TYPES:
        raise HTTPException(400, f"Type invalide. Valeurs acceptées : {', '.join(VALID_TYPES)}")
    intg = RmmIntegration(**body.model_dump())
    db.add(intg)
    await db.commit()
    await db.refresh(intg)
    return _out(intg)


@router.put("/{intg_id}", response_model=IntegrationOut)
async def update_integration(
    intg_id: int, body: IntegrationUpdate,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.rmm.write")),
):
    intg = (await db.execute(select(RmmIntegration).where(RmmIntegration.id == intg_id))).scalar_one_or_none()
    if not intg:
        raise HTTPException(404, "Intégration introuvable")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(intg, k, v)
    await db.commit()
    await db.refresh(intg)
    return _out(intg)


@router.delete("/{intg_id}", status_code=204)
async def delete_integration(
    intg_id: int,
    db:    AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settings.rmm.write")),
):
    intg = (await db.execute(select(RmmIntegration).where(RmmIntegration.id == intg_id))).scalar_one_or_none()
    if not intg:
        raise HTTPException(404, "Intégration introuvable")
    await db.delete(intg)
    await db.commit()


@router.post("/{intg_id}/sync")
async def sync_integration(
    intg_id: int,
    db:      AsyncSession = Depends(get_db),
    _user:   User = Depends(require_permission("settings.rmm.write")),
):
    """Déclenche une synchronisation immédiate."""
    intg = (await db.execute(select(RmmIntegration).where(RmmIntegration.id == intg_id))).scalar_one_or_none()
    if not intg:
        raise HTTPException(404, "Intégration introuvable")
    result = await run_sync(intg_id)
    if "error" in result:
        raise HTTPException(502, result["error"])
    return result
