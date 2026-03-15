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

# 2. Migrations dans l'ordre numérique (détection automatique)
for FILE in $(ls "$SQLDIR"/migration_v*.sql 2>/dev/null | sort -t 'v' -k2 -n); do
    v=$(echo "$FILE" | grep -oP 'v\K[0-9]+')
    echo "Grand-Duc: Migration v${v}..."
    psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$FILE"
done

echo "Grand-Duc: Base de données initialisée avec succès."
