# ─────────────────────────────────────────────────────────────────────────────
# Grand-Duc Frontend — Build Vue 3 + Nginx
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1 : Build ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
ARG VITE_APP_VERSION=docker
RUN VITE_APP_VERSION=${VITE_APP_VERSION} npm run build

# ── Stage 2 : Nginx ─────────────────────────────────────────────────────────
FROM nginx:alpine

# Supprimer la config par défaut
RUN rm /etc/nginx/conf.d/default.conf

# Config nginx : SPA + reverse-proxy /api → backend
COPY docker/nginx.conf /etc/nginx/conf.d/grand-duc.conf

# Copier le build Vue
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
