"""
Grand-Duc Admin — Backend FastAPI
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s  %(message)s")

from database import engine, Base
from config   import settings

logger = logging.getLogger(__name__)
from routers  import auth, rules, logs, stats, users, client_groups, client_users, tls_bypass, killswitch, certificates, proxy_control, integrations, roles
from routers  import settings as settings_router


async def _ensure_builtin_roles():
    """Crée les rôles built-in s'ils n'existent pas encore."""
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


async def _ensure_indexes():
    """Crée les index manquants sur access_logs (accélère le dashboard)."""
    from sqlalchemy import text
    indexes = [
        ("ix_access_logs_accessed_at",         "CREATE INDEX ix_access_logs_accessed_at ON access_logs (accessed_at)"),
        ("ix_access_logs_blocked_accessed_at", "CREATE INDEX ix_access_logs_blocked_accessed_at ON access_logs (blocked, accessed_at)"),
        ("ix_access_logs_client_ip",           "CREATE INDEX ix_access_logs_client_ip ON access_logs (client_ip)"),
        ("ix_access_logs_host",                "CREATE INDEX ix_access_logs_host ON access_logs (host)"),
    ]
    for name, sql in indexes:
        try:
            async with engine.begin() as conn:
                exists = await conn.scalar(text(
                    "SELECT 1 FROM pg_indexes WHERE indexname = :name"
                ).bindparams(name=name))
                if exists:
                    continue
                await conn.execute(text(sql))
                logger.info("Index %s créé", name)
        except Exception as exc:
            logger.warning("Index %s échoué : %s", name, exc)


async def _ensure_columns():
    """Ajoute les colonnes manquantes (migrations légères)."""
    from sqlalchemy import text
    migrations = [
        ("client_users", "logged_user", "ALTER TABLE client_users ADD COLUMN logged_user TEXT"),
        ("rmm_integrations", "auto_group_by", "ALTER TABLE rmm_integrations ADD COLUMN auto_group_by VARCHAR(20) DEFAULT 'none'"),
    ]
    for table, col, sql in migrations:
        try:
            async with engine.begin() as conn:
                exists = await conn.scalar(text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :col"
                ).bindparams(table=table, col=col))
                if not exists:
                    await conn.execute(text(sql))
                    logger.info("Migration : ajout colonne %s.%s", table, col)
        except Exception as exc:
            logger.warning(
                "Migration %s.%s échouée (droits insuffisants ?). "
                "Exécutez manuellement : %s   —   Erreur : %s",
                table, col, sql, exc,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables si absentes (utile en dev)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("create_all échoué (droits insuffisants ?). Erreur : %s", exc)
    await _ensure_columns()
    await _ensure_indexes()
    await _ensure_builtin_roles()
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
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ADMIN_CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Middlewares ASGI (pure ASGI — compatible avec les uploads & SSE) ──────────
from starlette.types import ASGIApp, Receive, Scope, Send
import time as _time

class TimingAndSecurityMiddleware:
    """Mesure le temps de chaque requête HTTP + ajoute les headers de sécurité."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        t0 = _time.time()
        path = scope.get("path", "?")
        method = scope.get("method", "?")
        status_code = 0

        async def send_with_extras(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                elapsed_ms = (_time.time() - t0) * 1000
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"server-timing", f"total;dur={elapsed_ms:.1f}".encode()),
                ]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_extras)
        elapsed_ms = (_time.time() - t0) * 1000
        logger.info("[HTTP] %s %s → %s en %.0f ms", method, path, status_code, elapsed_ms)

app.add_middleware(TimingAndSecurityMiddleware)

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

# uvicorn main:app --reload --port 8000
