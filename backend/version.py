"""
Version du backend Grand-Duc.

En Docker, la source de vérité est le label OCI `org.opencontainers.image.version`
gravé dans l'image par le workflow de publication : c'est lui qu'affiche la page
« Mises à jour ». `APP_VERSION` (injectée au build) puis la constante ci-dessous
ne servent que de repli, notamment en installation native sans Docker.

La constante doit suivre le tag git publié (les tags n'ont pas de préfixe `v`).
"""

import os

__version__ = "0.1.6"

VERSION = os.environ.get("APP_VERSION") or __version__
