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
from routers  import auth, rules, logs, stats, users, client_groups, client_users, tls_bypass, killswitch, certificates, proxy_control, integrations
from routers  import settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables si absentes (utile en dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

# uvicorn main:app --reload --port 8000
