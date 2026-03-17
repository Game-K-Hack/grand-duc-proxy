#!/bin/sh
set -e
mkdir -p grand-duc && cd grand-duc
curl -fsSL https://raw.githubusercontent.com/Game-K-Hack/grand-duc-proxy/main/docker-compose.prod.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/Game-K-Hack/grand-duc-proxy/main/.env.docker -o .env
docker compose --profile linux up -d
echo ""
echo "Grand-Duc est pret !"
echo "  Interface : http://localhost"
echo "  Proxy     : localhost:8080"
echo "  Login     : admin / admin"
