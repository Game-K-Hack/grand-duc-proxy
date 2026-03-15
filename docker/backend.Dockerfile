# ─────────────────────────────────────────────────────────────────────────────
# Grand-Duc Backend — Python 3.12 (slim)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

# Dépendances système : libpq pour psycopg2-binary, docker-cli pour contrôler le proxy
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        gnupg \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dépendances Python en premier (cache Docker)
# On remplace psycopg2 (compilation C) par psycopg2-binary (pré-compilé)
COPY backend/requirements.txt .
RUN sed 's/^psycopg2\r\?$/psycopg2-binary/' requirements.txt > requirements-docker.txt \
    && pip install --no-cache-dir -r requirements-docker.txt \
    && rm requirements-docker.txt

# Copier le code source
COPY backend/ .

# Supprimer le .env local s'il a été copié par erreur
RUN rm -f .env

# En Docker, le proxy tourne dans un conteneur séparé
# Le backend n'a pas besoin de gérer le processus proxy directement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
