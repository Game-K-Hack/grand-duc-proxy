"""
Accès au daemon Docker depuis le backend.

Comme `backend/routers/proxy_control.py`, on passe par le **binaire `docker`**
(installé dans l'image, cf. docker/backend.Dockerfile) et non par un SDK : pas
de dépendance supplémentaire, et le socket est déjà monté.

Le socket est monté `:ro` dans les deux fichiers compose. Ce `:ro` ne restreint
RIEN — il porte sur le fichier de socket, pas sur les échanges : l'API Docker
complète reste accessible, et elle équivaut à un accès root sur l'hôte. C'est
déjà le cas aujourd'hui pour `proxy.restart` ; les permissions applicatives sont
la seule barrière réelle.

Aucune commande n'est construite par concaténation : `subprocess.run` reçoit
toujours une liste d'arguments, jamais `shell=True`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

IN_DOCKER = os.path.exists("/.dockerenv")

# Préfixe des images publiées par le projet ; tout le reste est hors périmètre.
MANAGED_IMAGE_PREFIX = "ghcr.io/game-k-hack/grand-duc-proxy-"

SERVICE_LABELS = {
    "db":       "Base de données",
    "backend":  "Backend",
    "frontend":  "Interface web",
    "proxy":    "Proxy",
}


def docker(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )


def is_available() -> bool:
    """Le daemon Docker est-il joignable depuis ici ?"""
    if not IN_DOCKER:
        return False
    try:
        return docker("version", "--format", "{{.Server.Version}}", timeout=8).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _self_container_id() -> str | None:
    """Dans un conteneur, le hostname est l'ID court."""
    try:
        return Path("/etc/hostname").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def self_labels() -> dict[str, str]:
    """Labels du conteneur backend — c'est de là que vient tout le reste.

    `com.docker.compose.project.working_dir` donne le répertoire du projet **sur
    l'hôte**, que le backend ne peut pas ouvrir mais peut nommer (cf. updater).
    """
    cid = _self_container_id()
    if not cid:
        return {}
    res = docker("inspect", "--format", "{{json .Config.Labels}}", cid)
    if res.returncode != 0:
        logger.warning("Inspection du conteneur backend échouée : %s", res.stderr.strip())
        return {}
    try:
        return json.loads(res.stdout) or {}
    except ValueError:
        return {}


def project_info() -> dict:
    """Identité du projet compose auquel appartient ce backend."""
    labels = self_labels()
    files = labels.get("com.docker.compose.project.config_files") or ""
    return {
        "project":      labels.get("com.docker.compose.project"),
        "working_dir":  labels.get("com.docker.compose.project.working_dir"),
        "config_files": [f for f in files.split(",") if f.strip()],
    }


def project_containers(project: str) -> list[dict]:
    """Inspection complète des conteneurs du projet, en un seul appel."""
    res = docker(
        "ps", "-a",
        "--filter", f"label=com.docker.compose.project={project}",
        "--format", "{{.ID}}",
    )
    if res.returncode != 0:
        logger.warning("Listage des conteneurs échoué : %s", res.stderr.strip())
        return []
    ids = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if not ids:
        return []

    res = docker("inspect", "--format", "{{json .}}", *ids, timeout=30)
    if res.returncode != 0:
        logger.warning("Inspection des conteneurs échouée : %s", res.stderr.strip())
        return []

    out = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def describe_container(raw: dict) -> dict:
    """Extrait ce qui nous intéresse d'un `docker inspect`.

    La version vient du label OCI `org.opencontainers.image.version`, gravé par
    `docker/metadata-action` dans les images publiées. C'est la seule source
    exacte : le conteneur peut tourner sur le tag `latest`, le label dit quand
    même de quelle version il s'agit.
    """
    labels = (raw.get("Config") or {}).get("Labels") or {}
    image_ref = (raw.get("Config") or {}).get("Image") or ""
    state = raw.get("State") or {}

    managed = image_ref.startswith(MANAGED_IMAGE_PREFIX)
    oci_version = labels.get("org.opencontainers.image.version")

    # Une image construite par compose est nommée « <projet>-<service> », sans
    # registre ni tag — c'est l'absence de tag qui la distingue d'une image
    # publique comme « postgres:17-alpine ».
    tag = image_ref.rsplit(":", 1)[1] if ":" in image_ref.rsplit("/", 1)[-1] else None

    if managed:
        kind = "ghcr"
    elif tag is None:
        kind = "local-build"
    else:
        kind = "external"

    return {
        "service":    labels.get("com.docker.compose.service"),
        "container":  (raw.get("Name") or "").lstrip("/") or None,
        "image":      image_ref or None,
        "tag":        tag,
        "version":    oci_version,
        "revision":   labels.get("org.opencontainers.image.revision"),
        "running":    bool(state.get("Running")),
        "started_at": state.get("StartedAt"),
        "managed":    managed,
        "kind":       kind,
    }
