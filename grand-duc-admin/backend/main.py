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
        # Rôle Administrateur
        result = await db.execute(select(Role).where(Role.name == "Administrateur"))
        if not result.scalar_one_or_none():
            db.add(Role(name="Administrateur", description="Accès complet à toutes les fonctionnalités",
                        permissions=json.dumps(ADMIN_PERMISSIONS), is_builtin=True))
        # Rôle Lecteur
        result = await db.execute(select(Role).where(Role.name == "Lecteur"))
        if not result.scalar_one_or_none():
            db.add(Role(name="Lecteur", description="Consultation en lecture seule",
                        permissions=json.dumps(VIEWER_PERMISSIONS), is_builtin=True))
        await db.commit()

        # Assigner un rôle aux utilisateurs qui n'en ont pas
        admin_role = (await db.execute(select(Role).where(Role.name == "Administrateur"))).scalar_one()
        viewer_role = (await db.execute(select(Role).where(Role.name == "Lecteur"))).scalar_one()

        orphans = (await db.execute(select(User).where(User.role_id.is_(None)))).scalars().all()
        for u in orphans:
            u.role_id = admin_role.id if u.role == "admin" else viewer_role.id
        if orphans:
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables si absentes (utile en dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    allow_methods=["*"],
    allow_headers=["*"],
)

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
