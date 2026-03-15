# ─────────────────────────────────────────────────────────────────────────────
# Grand-Duc Proxy — Multi-stage build (binaire ~15-25 MB)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1 : Build ─────────────────────────────────────────────────────────
FROM rust:1.88-bookworm AS builder

WORKDIR /build

# Copier le manifeste en premier pour mettre en cache les deps
COPY proxy/Cargo.toml proxy/Cargo.lock* ./
# Créer un src factice pour compiler les deps seules
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true

# Copier le vrai code source et rebuild
COPY proxy/src ./src
# Invalider le cache du binaire factice
RUN touch src/main.rs
RUN cargo build --release

# ── Stage 2 : Runtime minimal ──────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier le binaire hors de /app (les volumes Docker montent sur /app)
COPY --from=builder /build/target/release/grand-duc-proxy /usr/local/bin/grand-duc-proxy

# Créer la structure de données
# /app/certs est monté via le volume certs (CA partagée avec le backend)
# /app/data  est monté via le volume proxy-data (logs partagés avec le backend)
RUN mkdir -p /app/templates/blocked /app/data /app/certs \
    && ln -sf /app/data/grand-duc.log /app/grand-duc.log \
    && ln -sf /app/certs/grand-duc-ca.key /app/grand-duc-ca.key \
    && ln -sf /app/certs/grand-duc-ca.crt /app/grand-duc-ca.crt

# GRAND_DUC_ROOT pointe vers /app pour que resolve_path() fonctionne
ENV GRAND_DUC_ROOT=/app
ENV RUST_LOG=grand_duc=info

# Le proxy écoute sur 8080 par défaut (configurable via PROXY_ADDR)
EXPOSE 8080

ENTRYPOINT ["grand-duc-proxy"]
