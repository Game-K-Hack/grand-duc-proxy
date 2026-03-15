#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Grand-Duc — Initialisation DB Docker
# Exécute init.sql puis les migrations dans l'ordre numérique correct.
# Ce script est lancé par PostgreSQL via docker-entrypoint-initdb.d
# ─────────────────────────────────────────────────────────────────────────────
set -e

SQLDIR=/docker-entrypoint-initdb.d/SQL

echo "Grand-Duc: Initialisation de la base de données..."

# 1. Schéma de base
psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$SQLDIR/init.sql"

# 1b. Colonne host manquante dans init.sql (définie dans le modèle SQLAlchemy)
psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS host TEXT;
SQL

# 2. Migrations dans l'ordre numérique
for v in 2 3 4 5 6 7 8 9 10 11 12 13; do
    FILE="$SQLDIR/migration_v${v}.sql"
    if [ -f "$FILE" ]; then
        echo "Grand-Duc: Migration v${v}..."
        psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$FILE"
    fi
done

echo "Grand-Duc: Base de données initialisée avec succès."
