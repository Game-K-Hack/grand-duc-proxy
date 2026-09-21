#!/bin/sh
set -e

REPO=Game-K-Hack/grand-duc-proxy
RAW=https://raw.githubusercontent.com/$REPO/main

mkdir -p grand-duc && cd grand-duc

# Le compose est toujours rafraîchi : c'est lui qui porte l'épinglage de version.
curl -fsSL "$RAW/docker-compose.prod.yml" -o docker-compose.yml

# Le .env, lui, n'est JAMAIS écrasé : il contient le mot de passe de la base et
# la clé secrète. Une réinstallation ne doit pas les réinitialiser.
if [ ! -f .env ]; then
    curl -fsSL "$RAW/.env.docker" -o .env
fi

# Version cible = dernière release publiée, repli sur `latest`.
TAG=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
      | sed -n 's/.*"tag_name"[ ]*:[ ]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$TAG" ] || TAG=latest

if grep -q '^GRAND_DUC_VERSION=' .env; then
    sed -i "s|^GRAND_DUC_VERSION=.*|GRAND_DUC_VERSION=$TAG|" .env
else
    printf '\nGRAND_DUC_VERSION=%s\n' "$TAG" >> .env
fi

# Le pull explicite : sans lui, une réinstallation sur une machine possédant
# déjà les images garderait indéfiniment les anciennes.
docker compose --profile linux pull
docker compose --profile linux up -d

echo ""
echo "Grand-Duc $TAG est pret !"
echo "  Interface : http://localhost"
echo "  Proxy     : localhost:8080"
echo ""
echo "Les mises a jour suivantes se font depuis Administration > Mises a jour."
