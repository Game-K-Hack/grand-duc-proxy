"""
Grand-Duc Admin — Backend FastAPI
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
import logging

from database import engine, Base
from config   import settings
from version  import VERSION

logger = logging.getLogger(__name__)
from routers  import auth, rules, logs, stats, users, client_groups, client_users, tls_bypass, killswitch, certificates, proxy_control, integrations, roles, updates
from routers  import settings as settings_router


async def _ensure_builtin_roles():
    """Crée les rôles built-in, et réconcilie leurs permissions.

    La réconciliation est ADDITIVE : on ajoute les clés absentes, on ne retire
    ni ne modifie jamais une clé déjà présente. Sans elle, une permission
    introduite par une nouvelle version resterait inaccessible sur toute
    installation existante — les rôles n'étaient créés qu'une fois, et les
    migrations SQL ne sont jouées qu'à la création du volume PostgreSQL.
    C'est ce qui a imposé le rattrapage manuel de SQL/migration_v13.sql:28-33.
    """
    import json
    from sqlalchemy import select
    from database import AsyncSessionLocal
    from models import Role, User
    from permissions import ADMIN_PERMISSIONS, VIEWER_PERMISSIONS

    async with AsyncSessionLocal() as db:
        # Charger tous les rôles builtin en 1 requête
        result = await db.execute(select(Role).where(Role.is_builtin == True))
        existing = {r.name: r for r in result.scalars().all()}

        if "Administrateur" not in existing:
            db.add(Role(name="Administrateur", description="Accès complet à toutes les fonctionnalités",
                        permissions=json.dumps(ADMIN_PERMISSIONS), is_builtin=True))
        if "Lecteur" not in existing:
            db.add(Role(name="Lecteur", description="Consultation en lecture seule",
                        permissions=json.dumps(VIEWER_PERMISSIONS), is_builtin=True))

        for name, reference in (("Administrateur", ADMIN_PERMISSIONS), ("Lecteur", VIEWER_PERMISSIONS)):
            role = existing.get(name)
            if role is None:
                continue
            try:
                current = json.loads(role.permissions) or {}
            except (ValueError, TypeError):
                logger.warning("Permissions illisibles pour le rôle %s — réinitialisation", name)
                current = {}
            added = [k for k in reference if k not in current]
            if added:
                current.update({k: reference[k] for k in added})
                role.permissions = json.dumps(current)
                logger.info("Rôle %s : %d permission(s) ajoutée(s) — %s", name, len(added), ", ".join(added))

        await db.commit()

        # Assigner un rôle aux utilisateurs orphelins
        orphans = (await db.execute(select(User).where(User.role_id.is_(None)))).scalars().all()
        if orphans:
            # Recharger les rôles si on vient de les créer
            if "Administrateur" not in existing or "Lecteur" not in existing:
                result = await db.execute(select(Role).where(Role.is_builtin == True))
                existing = {r.name: r for r in result.scalars().all()}
            admin_role = existing["Administrateur"]
            viewer_role = existing["Lecteur"]
            for u in orphans:
                u.role_id = admin_role.id if u.role == "admin" else viewer_role.id
            await db.commit()


async def _notify_if_updated():
    """Signale une mise à jour appliquée, au démarrage qui suit.

    Le backend qui reçoit POST /api/updates/apply est détruit quelques secondes
    plus tard par l'updater : il ne peut pas émettre la notification lui-même.
    On compare donc la version courante à la dernière version enregistrée.
    """
    import json
    from database import AsyncSessionLocal
    from models import AppSetting

    async with AsyncSessionLocal() as db:
        row = await db.get(AppSetting, "installed_version")
        previous = row.value if row else None

        if previous == VERSION:
            return

        if row:
            row.value = VERSION
        else:
            db.add(AppSetting(key="installed_version", value=VERSION))
        await db.commit()

        # Premier démarrage : on initialise sans prétendre qu'il y a eu une
        # mise à jour.
        if previous is None:
            return

        req = await db.get(AppSetting, "update_request")
        who = "—"
        if req:
            try:
                who = (json.loads(req.value) or {}).get("requested_by") or "—"
            except ValueError:
                pass

    from services.email import notify
    asyncio.create_task(notify(
        "update_applied",
        f"Grand-Duc mis à jour en {VERSION}",
        [f"Version précédente : <strong>{previous}</strong>",
         f"Nouvelle version : <strong>{VERSION}</strong>",
         f"Demandée par : {who}"],
    ))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables si absentes (utile en dev)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("create_all échoué (droits insuffisants ?). Erreur : %s", exc)
    # Avant tout le reste : le schéma doit correspondre au code qui va tourner.
    from services.migrations import run_migrations
    await run_migrations()
    await _ensure_builtin_roles()
    await _notify_if_updated()
    integrations.start_sync_loop()
    _rule_task = asyncio.create_task(_rule_check_loop())
    yield
    _rule_task.cancel()
    integrations.stop_sync_loop()
    await engine.dispose()


async def _rule_check_loop():
    """Vérifie toutes les 5 minutes si des règles surveillées ont été déclenchées."""
    from services.email import check_rule_triggers
    while True:
        try:
            await asyncio.sleep(300)
            await check_rule_triggers()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Erreur boucle surveillance règles : %s", exc)


app = FastAPI(
    title="Grand-Duc Admin API",
    version=VERSION,
    lifespan=lifespan,
)


@app.get("/api/health", tags=["Système"])
async def health():
    """Sonde de santé NON authentifiée.

    Sert au frontend pour détecter le retour du backend pendant une mise à jour,
    moment où il n'y a ni jeton exploitable ni garantie que l'API réponde.
    """
    return {"status": "ok", "version": VERSION}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ADMIN_CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Security headers middleware (pure ASGI — compatible avec les uploads) ─────
from starlette.types import ASGIApp, Receive, Scope, Send

class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                ]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router,  prefix="/api/auth",  tags=["Auth"])
app.include_router(rules.router, prefix="/api/rules", tags=["Règles"])
app.include_router(logs.router,  prefix="/api/logs",  tags=["Logs"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistiques"])
app.include_router(users.router, prefix="/api/users", tags=["Utilisateurs"])
app.include_router(client_groups.router, prefix="/api/client-groups", tags=["Groupes clients"])
app.include_router(client_users.router,  prefix="/api/client-users",  tags=["Utilisateurs clients"])
app.include_router(tls_bypass.router,    prefix="/api/tls-bypass",    tags=["TLS Bypass"])
app.include_router(killswitch.router,    prefix="/api/killswitch",    tags=["Killswitch"])
app.include_router(certificates.router,   prefix="/api/certificates",  tags=["Certificats"])
app.include_router(proxy_control.router,  prefix="/api/proxy",         tags=["Proxy"])
app.include_router(integrations.router,  prefix="/api/integrations",  tags=["Intégrations RMM"])
app.include_router(settings_router.router, prefix="/api/settings",     tags=["Paramètres"])
app.include_router(roles.router,           prefix="/api/roles",        tags=["Rôles"])
app.include_router(updates.router,         prefix="/api/updates",      tags=["Mises à jour"])

# uvicorn main:app --reload --port 8000
