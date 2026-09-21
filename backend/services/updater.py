"""
Lancement et suivi de la mise à jour.

Le backend ne peut pas se mettre à jour lui-même : `docker compose up -d backend`
détruit le processus qui a lancé la commande avant qu'elle ne se termine. On
délègue donc à un conteneur **hors de la stack**, qui survit à la recréation de
tous les services.

Ce conteneur n'est PAS lancé avec `--rm` : une fois sorti, il reste en place et
c'est le backend recréé qui lit son code de sortie et ses logs. Autrement dit,
**le conteneur est le journal** — inutile de prévoir un volume ou une table.

Le bind mount du répertoire du projet fonctionne alors même que le backend ne
voit pas ce chemin : `-v <src>:<dst>` est interprété par le daemon Docker, qui
tourne sur l'hôte. Le backend se contente de nommer le chemin, il ne l'ouvre
jamais. C'est le piège classique du Docker-out-of-Docker — un chemin *interne*
au conteneur backend serait faux.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import PurePosixPath

from services.docker_cli import docker

logger = logging.getLogger(__name__)

CONTAINER_NAME = "grand-duc-updater"
UPDATER_IMAGE = "docker:27-cli"

VERSION_RE = re.compile(r"^(latest|v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?)$")

# Échappements de test, sans toucher à la stack. Activés par variable
# d'environnement uniquement — jamais exposés à l'API.
DRY_RUN = os.environ.get("GRAND_DUC_UPDATER_DRY_RUN") == "1"
FORCE = os.environ.get("GRAND_DUC_FORCE_UPDATE") == "1"

# Script constant : aucune donnée n'y est interpolée, tout passe par -e.
_SCRIPT = r"""
set -u
say() { echo "::gd::$1"; }

# Laisse la réponse 202 atteindre le navigateur avant de couper le backend.
sleep 3
say "start target=$GD_TARGET"

[ -f docker-compose.yml ] || { say "fail compose-missing"; exit 4; }

STAMP=$(date +%s)
cp .env ".env.bak.$STAMP" 2>/dev/null
cp docker-compose.yml "docker-compose.yml.bak.$STAMP" 2>/dev/null

restore() {
  [ -f ".env.bak.$STAMP" ] && cp ".env.bak.$STAMP" .env
  [ -f "docker-compose.yml.bak.$STAMP" ] && cp "docker-compose.yml.bak.$STAMP" docker-compose.yml
  return 0
}

# Installation encore figée sur le tag `latest` : on récupère le compose DU TAG
# ciblé, donc cohérent avec les images que l'on s'apprête à installer.
if [ "$GD_REFRESH_COMPOSE" = "1" ] && [ "$GD_TARGET" != "latest" ]; then
  if wget -qO .compose.new \
      "https://raw.githubusercontent.com/Game-K-Hack/grand-duc-proxy/refs/tags/$GD_TARGET/docker-compose.prod.yml" \
     && grep -q 'GRAND_DUC_VERSION' .compose.new; then
    mv .compose.new docker-compose.yml
    say "compose-refreshed"
  else
    say "compose-kept"
  fi
  rm -f .compose.new
fi

touch .env
if grep -q '^GRAND_DUC_VERSION=' .env; then
  sed -i "s|^GRAND_DUC_VERSION=.*|GRAND_DUC_VERSION=$GD_TARGET|" .env
else
  printf '\nGRAND_DUC_VERSION=%s\n' "$GD_TARGET" >> .env
fi
say "env GRAND_DUC_VERSION=$GD_TARGET"

set -- -p "$GD_PROJECT"
for f in $GD_COMPOSE_FILES; do set -- "$@" -f "$f"; done
[ -n "$GD_PROFILE" ] && set -- "$@" --profile "$GD_PROFILE"

# Le pull d'abord : l'échec le plus probable (registre injoignable, tag
# inexistant, disque plein) survient alors que la stack tourne encore.
# Surtout : jamais --remove-orphans, qui supprimerait le conteneur proxy
# lorsque son profil n'est pas activé.
if [ "$GD_DRY_RUN" = "1" ]; then
  say "dry-run pull"
else
  docker compose "$@" pull || { restore; say "fail pull"; exit 2; }
fi
say "pulled"

if [ "$GD_DRY_RUN" = "1" ]; then
  say "dry-run up"
else
  docker compose "$@" up -d || { say "fail up"; exit 3; }
fi

say "done"
exit 0
"""


def valid_version(tag: str) -> bool:
    return bool(VERSION_RE.match((tag or "").strip()))


def valid_working_dir(path: str | None) -> bool:
    """Le chemin vient des labels Docker, jamais du client — on le vérifie quand même."""
    if not path or "\n" in path or "\r" in path or ".." in path:
        return False
    return path.startswith("/") or bool(re.match(r"^[A-Za-z]:[\\/]", path))


def is_windows_host_path(path: str | None) -> bool:
    """Chemin hôte Windows (« D:\\… ») — impossible à monter au même chemin.

    L'updater doit monter le répertoire du projet À SON CHEMIN D'ORIGINE (voir
    `launch`), or un conteneur Linux n'accepte pas « D:\\… » comme point de
    montage ni comme répertoire de travail. On le détecte pour refuser
    proprement, plutôt que de laisser `docker run` échouer sur un message
    obscur.
    """
    return bool(path and re.match(r"^[A-Za-z]:[\\/]", path))


def ensure_image() -> tuple[bool, str | None]:
    """Garantit la présence de l'image updater AVANT de répondre 202.

    C'est le seul point qui dépend de Docker Hub et non de GHCR : si le pull
    échoue, mieux vaut le dire tout de suite que laisser un updater introuvable.
    """
    if docker("image", "inspect", UPDATER_IMAGE, timeout=15).returncode == 0:
        return True, None
    logger.info("Téléchargement de l'image updater %s…", UPDATER_IMAGE)
    res = docker("pull", UPDATER_IMAGE, timeout=180)
    if res.returncode == 0:
        return True, None
    return False, (res.stderr or "").strip()[:300]


def launch(*, target: str, project: str, working_dir: str,
           config_files: list[str], with_proxy_profile: bool,
           refresh_compose: bool, requested_by: str) -> tuple[bool, str | None]:
    """Démarre l'updater détaché. Retourne (ok, erreur)."""
    # Le run précédent sert de journal jusqu'au suivant : on ne le supprime
    # qu'ici, juste avant d'en créer un nouveau.
    docker("rm", "-f", CONTAINER_NAME, timeout=20)

    # Les labels donnent des chemins absolus côté hôte. Comme l'updater a pour
    # répertoire de travail celui du projet, on ne garde que les noms de
    # fichiers : c'est portable et insensible au séparateur Windows/Linux.
    files = " ".join(
        PurePosixPath(f.replace("\\", "/")).name for f in config_files
    ) or "docker-compose.yml"

    args = [
        "run", "-d",
        "--name", CONTAINER_NAME,
        "--label", f"com.grandduc.target={target}",
        "--label", f"com.grandduc.requested-by={requested_by}",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        # Monté AU MÊME CHEMIN, et non sur un /project générique : compose grave
        # son répertoire de travail dans le label
        # `com.docker.compose.project.working_dir` des conteneurs qu'il recrée.
        # Un chemin générique rendrait ce label faux et casserait la mise à jour
        # SUIVANTE, qui ne retrouverait plus le projet sur l'hôte.
        # Corollaire : sous Docker Desktop Windows, où le chemin hôte est de la
        # forme « D:\… », ce montage est impossible dans un conteneur Linux.
        # Sans conséquence : Windows est un mode de développement, où
        # `can_update` vaut déjà False.
        "-v", f"{working_dir}:{working_dir}",
        "-w", working_dir,
        "-e", f"GD_TARGET={target}",
        "-e", f"GD_PROJECT={project}",
        "-e", f"GD_PROFILE={'linux' if with_proxy_profile else ''}",
        "-e", f"GD_COMPOSE_FILES={files}",
        "-e", f"GD_REFRESH_COMPOSE={'1' if refresh_compose else '0'}",
        "-e", f"GD_DRY_RUN={'1' if DRY_RUN else '0'}",
        "--entrypoint", "/bin/sh",
        UPDATER_IMAGE, "-c", _SCRIPT,
    ]
    res = docker(*args, timeout=30)
    if res.returncode != 0:
        return False, (res.stderr or "").strip()[:300]
    logger.info("Updater lancé vers %s par %s", target, requested_by)
    return True, None


def progress() -> dict:
    """État de la mise à jour, lisible même après recréation du backend."""
    res = docker("inspect", "--format", "{{json .}}", CONTAINER_NAME, timeout=15)
    if res.returncode != 0:
        return {"state": "idle", "target": None, "requested_by": None,
                "exit_code": None, "started_at": None, "finished_at": None,
                "steps": [], "log": []}

    import json as _json
    try:
        raw = _json.loads(res.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return {"state": "idle", "target": None, "requested_by": None,
                "exit_code": None, "started_at": None, "finished_at": None,
                "steps": [], "log": []}

    state = raw.get("State") or {}
    labels = (raw.get("Config") or {}).get("Labels") or {}
    running = bool(state.get("Running"))
    exit_code = state.get("ExitCode")

    logs = docker("logs", "--tail", "200", CONTAINER_NAME, timeout=15)
    lines = [l for l in (logs.stdout + logs.stderr).splitlines() if l.strip()]
    steps = [l.split("::gd::", 1)[1].strip() for l in lines if "::gd::" in l]

    if running:
        verdict = "running"
    elif exit_code == 0:
        verdict = "success"
    else:
        verdict = "failed"

    return {
        "state":        verdict,
        "target":       labels.get("com.grandduc.target"),
        "requested_by": labels.get("com.grandduc.requested-by"),
        "exit_code":    None if running else exit_code,
        "started_at":   state.get("StartedAt"),
        "finished_at":  None if running else state.get("FinishedAt"),
        "steps":        steps,
        "log":          lines[-200:],
    }
