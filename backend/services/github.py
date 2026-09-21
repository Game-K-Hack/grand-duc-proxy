"""
Vérification des versions publiées sur GitHub.

Le cache vit dans `app_settings` et non en mémoire : une mise à jour **recrée le
conteneur backend**, donc un cache mémoire serait vidé précisément au moment où
l'on veut relire l'état d'après. Il permet aussi d'afficher quelque chose quand
GitHub est injoignable.

Quota non authentifié : 60 requêtes/heure **par IP sortante** — vite consommé
derrière le NAT d'une entreprise. D'où l'ETag (les 304 ne sont pas décomptées)
et le TTL de 6 heures.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSetting
from version import VERSION

logger = logging.getLogger(__name__)

REPO = "Game-K-Hack/grand-duc-proxy"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"

CACHE_KEY = "update_check"
TTL_SECONDS = 6 * 3600
MIN_INTERVAL = 60          # garde anti-martèlement sur la vérification manuelle

# Les tags du dépôt n'ont pas de préfixe `v` (0.1.0 … 0.1.6) mais le workflow
# de publication accepte les deux formes.
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?$")


def normalize(tag: str | None) -> str | None:
    if not tag:
        return None
    return tag.lstrip("vV")


def parse(tag: str | None) -> tuple | None:
    """Tuple comparable, ou None si le tag n'est pas une version sémantique."""
    if not tag:
        return None
    m = _VERSION_RE.match(tag.strip())
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    # Une pré-release précède la release du même numéro.
    return (int(major), int(minor), int(patch), 0 if pre else 1, pre or "")


def compare(local: str | None, remote: str | None) -> str:
    """`outdated`, `up_to_date`, `ahead`, ou `unknown` si incomparable.

    `latest` et `dev` ne sont pas des versions : on ne peut rien en conclure.
    """
    a, b = parse(local), parse(remote)
    if a is None or b is None:
        return "unknown"
    if a < b:
        return "outdated"
    if a > b:
        return "ahead"
    return "up_to_date"


async def _load(db: AsyncSession) -> dict:
    row = await db.get(AppSetting, CACHE_KEY)
    if not row:
        return {}
    try:
        return json.loads(row.value) or {}
    except ValueError:
        return {}


async def _store(db: AsyncSession, data: dict) -> None:
    payload = json.dumps(data)
    row = await db.get(AppSetting, CACHE_KEY)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=CACHE_KEY, value=payload))
    await db.commit()


def _age(cached: dict) -> float:
    ts = cached.get("checked_at_epoch")
    return time.time() - ts if ts else float("inf")


async def get_latest(db: AsyncSession, force: bool = False) -> dict:
    """Dernière release publiée, depuis le cache ou GitHub.

    Ne lève jamais : un échec réseau renseigne `error` et sert le cache périmé.
    """
    cached = await _load(db)
    age = _age(cached)

    if not force and age < TTL_SECONDS and cached.get("tag"):
        return cached
    if force and age < MIN_INTERVAL:
        return cached

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"grand-duc-proxy/{VERSION}",
    }
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]

    now = datetime.now(timezone.utc)
    result = dict(cached)
    result.update({
        "checked_at": now.isoformat(),
        "checked_at_epoch": time.time(),
        "error": None,
        "rate_limited": False,
        "rate_reset": None,
    })

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(API, headers=headers)

        if resp.status_code == 304:
            # Non décomptée du quota : on garde le contenu, on rafraîchit la date.
            logger.debug("GitHub : pas de nouvelle release (304)")

        elif resp.status_code == 200:
            data = resp.json()
            result.update({
                "etag":         resp.headers.get("ETag"),
                "tag":          data.get("tag_name"),
                "name":         data.get("name"),
                "html_url":     data.get("html_url") or RELEASES_URL,
                "published_at": data.get("published_at"),
                "notes":        (data.get("body") or "")[:4000],
                "assets": [
                    {"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size")}
                    for a in (data.get("assets") or [])
                ],
            })

        elif resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = resp.headers.get("X-RateLimit-Reset")
            result["rate_limited"] = True
            result["rate_reset"] = int(reset) if reset and reset.isdigit() else None
            logger.warning("GitHub : quota atteint, réinitialisation à %s", result["rate_reset"])

        elif resp.status_code == 404:
            # Dépôt sans release publiée : ce n'est pas une panne.
            result["error"] = "no_release"

        else:
            result["error"] = f"http_{resp.status_code}"
            logger.warning("GitHub : réponse inattendue %s", resp.status_code)

    except (httpx.HTTPError, ValueError) as exc:
        result["error"] = "offline"
        logger.info("GitHub injoignable : %s", exc)

    await _store(db, result)
    return result


def is_stale(cached: dict) -> bool:
    return _age(cached) > TTL_SECONDS
