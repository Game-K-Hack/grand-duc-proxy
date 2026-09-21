"""
Application des migrations SQL au démarrage du backend.

`docker/docker-init-db.sh` ne s'exécute qu'à la CRÉATION du volume PostgreSQL
(il est monté dans `docker-entrypoint-initdb.d`). Sur une installation déjà en
service, une nouvelle migration n'était donc jamais appliquée : il fallait la
passer à la main via psql. Avec un système de mise à jour qui livre des
migrations à chaque version, cela installerait un backend en avance sur son
schéma à chaque fois.

Ce module tient un registre `schema_migrations` et applique ce qui manque, dans
l'ordre numérique, chacune dans sa transaction et **avec arrêt sur erreur** —
contrairement au script d'init qui tourne en `ON_ERROR_STOP=0` et masque tout.

`docker-init-db.sh` reste en place pour les volumes neufs ; le runner constatera
simplement que tout est déjà appliqué.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import text

from database import engine

logger = logging.getLogger(__name__)

# SQL/ est copié dans l'image backend ; en dev le dépôt est le parent de backend/
_SQL_DIRS = [Path("/app/SQL"), Path(__file__).resolve().parents[2] / "SQL"]

_MIGRATION_RE = re.compile(r"^migration_v(\d+)\.sql$")

# Migrations livrées avant l'existence de ce registre. Si le schéma est déjà
# peuplé quand on crée la table, elles sont marquées comme appliquées : les
# rejouer sur une base vivante serait au mieux inutile, au pire destructeur.
_LEGACY_MAX = 16

# Présence de cette table = le schéma a déjà été initialisé et migré jusqu'à v16
# (elle est créée par migration_v16, la dernière d'avant le registre).
_LEGACY_PROBE = "client_user_ips"


def _sql_dir() -> Path | None:
    for d in _SQL_DIRS:
        if d.is_dir():
            return d
    return None


def _discover(directory: Path) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for f in directory.iterdir():
        m = _MIGRATION_RE.match(f.name)
        if m:
            found.append((int(m.group(1)), f))
    return sorted(found)


async def run_migrations() -> None:
    """Applique les migrations manquantes. Lève si l'une d'elles échoue."""
    directory = _sql_dir()
    if directory is None:
        logger.warning("Migrations : dossier SQL introuvable (%s) — étape ignorée",
                       ", ".join(str(d) for d in _SQL_DIRS))
        return

    migrations = _discover(directory)
    if not migrations:
        logger.warning("Migrations : aucun fichier migration_v*.sql dans %s", directory)
        return

    async with engine.begin() as conn:
        created = (await conn.execute(text(
            "SELECT to_regclass('public.schema_migrations') IS NULL"
        ))).scalar()

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

        if created:
            already_initialised = (await conn.execute(text(
                "SELECT to_regclass('public.%s') IS NOT NULL" % _LEGACY_PROBE
            ))).scalar()
            if already_initialised:
                legacy = [v for v, _ in migrations if v <= _LEGACY_MAX]
                for v in legacy:
                    await conn.execute(
                        text("INSERT INTO schema_migrations (version) VALUES (:v) "
                             "ON CONFLICT DO NOTHING"),
                        {"v": v},
                    )
                logger.info("Migrations : registre initialisé, v%s→v%s marquées comme "
                            "déjà appliquées (base existante)", legacy[0], legacy[-1])

        applied = set((await conn.execute(
            text("SELECT version FROM schema_migrations")
        )).scalars().all())

    pending = [(v, f) for v, f in migrations if v not in applied]
    if not pending:
        logger.info("Migrations : schéma à jour (v%s)", max(applied) if applied else "—")
        return

    for version, path in pending:
        sql = path.read_text(encoding="utf-8")
        logger.info("Migrations : application de v%s…", version)
        try:
            # Une transaction par migration : un échec n'en laisse aucune à moitié
            # appliquée, et la suivante n'est pas tentée.
            async with engine.begin() as conn:
                # asyncpg prépare les requêtes, et une requête préparée ne peut
                # contenir qu'une seule commande. Un fichier de migration en
                # contient forcément plusieurs : on passe donc par la connexion
                # brute, dont `execute()` sans paramètre utilise le protocole
                # simple et accepte un script entier. Elle partage la
                # transaction ouverte par SQLAlchemy juste au-dessus.
                raw = await conn.get_raw_connection()
                await raw.driver_connection.execute(sql)
                await conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                    {"v": version},
                )
        except Exception:
            logger.exception("Migrations : ÉCHEC de v%s (%s) — démarrage interrompu",
                             version, path.name)
            raise
        logger.info("Migrations : v%s appliquée", version)

    logger.info("Migrations : %d migration(s) appliquée(s)", len(pending))
