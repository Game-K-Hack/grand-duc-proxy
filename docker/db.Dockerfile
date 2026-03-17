# ─────────────────────────────────────────────────────────────────────────────
# Grand-Duc DB — PostgreSQL 17 + migrations embarquées
# ─────────────────────────────────────────────────────────────────────────────
FROM postgres:17-alpine

# Copier les fichiers SQL et le script d'init
COPY SQL/ /docker-entrypoint-initdb.d/SQL/
COPY docker/docker-init-db.sh /docker-entrypoint-initdb.d/01-init.sh

# S'assurer que le script est exécutable et en LF
RUN chmod +x /docker-entrypoint-initdb.d/01-init.sh \
    && sed -i 's/\r$//' /docker-entrypoint-initdb.d/01-init.sh
