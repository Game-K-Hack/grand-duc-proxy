![banner](./frontend/src/assets/claudebanner.png)

![banner](./frontend/src/assets/banner.png)

```bash
curl -fsSL https://raw.githubusercontent.com/Game-K-Hack/grand-duc-proxy/main/install.sh | sh
```

> Proxy HTTP/HTTPS d'entreprise en Rust — filtrage intelligent, interception TLS, interface d'administration complète. Une commande, c'est pret.

---

## Architecture

| Composant | Techno | Rôle |
|---|---|---|
| **Proxy** | Rust (hudsucker + rustls + tokio) | Filtrage HTTP/HTTPS, terminaison TLS, CA dynamique |
| **Backend** | Python 3.12 (FastAPI + SQLAlchemy) | API REST d'administration |
| **Frontend** | Vue.js 3 (Vite + Pinia) | Interface web de gestion |
| **Database** | PostgreSQL 17 | Règles, logs, utilisateurs, configuration |

---

## Installation rapide

### Option A — Windows (développement, sans Docker)

#### Prérequis

- **PostgreSQL** 17+ installé et démarré
- **Rust** ≥ 1.88 (`rustup update stable`)
- **Python** 3.12+
- **Node.js** 20+

#### 1. Cloner le projet

```bash
git clone https://github.com/votre-org/grand-duc.git
cd grand-duc
```

#### 2. Initialiser la base de données

```bash
createdb -U postgres grand_duc
psql -U postgres -d grand_duc -f SQL/init.sql
```

Puis exécuter les migrations dans l'ordre :

```bash
for file in SQL/migration_v*.sql; do
    psql -U postgres -d grand_duc -f "$file"
done
```

Ou sous PowerShell :

```powershell
Get-ChildItem SQL\migration_v*.sql | Sort-Object { [int]($_.BaseName -replace '\D') } | ForEach-Object {
    psql -U postgres -d grand_duc -f $_.FullName
}
```

#### 3. Configurer les variables d'environnement

Copier `.env.example` en `.env` et adapter :

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre_mdp
POSTGRES_DB=grand_duc

DATABASE_URL=postgresql+asyncpg://postgres:votre_mdp@localhost/grand_duc
DATABASE_URL_PROXY=postgresql://postgres:votre_mdp@localhost/grand_duc
SECRET_KEY=une_cle_secrete_aleatoire

PROXY_ADDR=0.0.0.0:8080
RUST_LOG=grand_duc=info
```

#### 4. Lancer le backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### 5. Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

L'interface est accessible sur `http://localhost:5173`.

#### 6. Compiler et lancer le proxy

```bash
cd proxy
cargo build --release
./target/release/grand-duc-proxy.exe
```

Le proxy écoute sur `0.0.0.0:8080` par défaut.

---

### Option B — Linux (production, Docker)

#### Prérequis

- **Docker** et **Docker Compose** v2

#### Installation en une commande

```bash
git clone https://github.com/Game-K-Hack/grand-duc-proxy.git && cd grand-duc-proxy && docker compose --profile linux up --build -d
```

Cela démarre les 4 services :
- **db** : PostgreSQL 17 (initialisé automatiquement avec les migrations)
- **backend** : API FastAPI sur le réseau interne
- **frontend** : Nginx sur le port 80
- **proxy** : Binaire Rust en `network_mode: host` (port 8080)

#### Commandes utiles

```bash
# Voir les logs
docker compose --profile linux logs -f

# Rebuild après modification du code
docker compose --profile linux down
docker compose --profile linux up --build

# Reset complet (supprime la DB ET le certificat CA — voir « Mise à jour »)
docker compose --profile linux down -v
docker compose --profile linux up --build

# En cas de port déjà utilisé
docker compose --profile linux down
sudo killall docker-proxy 2>/dev/null
sudo systemctl restart docker
sleep 3
docker compose --profile linux up --build
```

#### Réseau Docker

```
┌─────────────────────────────────────────────────┐
│                  host network                   │
│  ┌──────────┐                                   │
│  │  proxy   │ :8080  (network_mode: host)       │
│  └────┬─────┘                                   │
│       │ localhost:5432                          │
├───────┼─────────────────────────────────────────┤
│       │       backend-net (bridge)              │
│  ┌────┴─────┐      ┌──────────┐                 │
│  │    db    │◄─────│ backend  │ :8000           │
│  └──────────┘      └────┬─────┘                 │
│                         │ frontend-net          │
│                    ┌────┴─────┐                 │
│                    │ frontend │ :80             │
│                    └──────────┘                 │
└─────────────────────────────────────────────────┘
```

---

## Mise à jour

Le plus simple est le bouton **Administration → Mises à jour** dans l'interface :
il télécharge les nouvelles images et recrée les services. Les instructions qui
suivent couvrent la mise à jour manuelle, depuis le serveur.

Toutes les commandes sont à lancer **depuis le répertoire du projet** (celui qui
contient `docker-compose.yml` et `.env`, créé par `install.sh` sous le nom
`grand-duc`).

### Mettre à jour en conservant les données

C'est le cas normal : règles, groupes, postes clients, journaux, comptes et
certificat CA sont préservés.

```bash
# Optionnel : viser une version précise plutôt que la dernière
# (sans cette ligne, la version déjà inscrite dans .env est conservée)
sed -i 's|^GRAND_DUC_VERSION=.*|GRAND_DUC_VERSION=0.1.6|' .env

docker compose --profile linux pull
docker compose --profile linux up -d
```

Les migrations de base de données sont appliquées **automatiquement** par le
backend à son démarrage : il tient un registre `schema_migrations` et ne rejoue
que ce qui manque. Pour le vérifier :

```bash
docker compose logs backend | grep -i migration
docker compose exec -T db psql -U hibou -d grand_duc   -c "SELECT version, applied_at FROM schema_migrations ORDER BY version;"
```

> ⚠️ N'utilisez **pas** `--remove-orphans`. Le service `proxy` vit sous le profil
> `linux` : sans `--profile linux`, cette option le supprimerait purement et
> simplement.

### Mettre à jour en repartant d'une base vierge

`down -v` supprime **tous** les volumes du projet, pas seulement la base :

| Volume | Contenu perdu |
|---|---|
| `pgdata` | Règles, groupes, postes clients, journaux d'accès, comptes et rôles |
| `certs` | **Le certificat CA** — un nouveau sera généré au redémarrage |
| `proxy-data` | Journaux du proxy |

> ⚠️ La perte du CA est la conséquence la plus lourde : le nouveau certificat
> devra être redéployé sur **tous les postes clients**, sinon le filtrage HTTPS
> cessera de fonctionner pour eux. Sauvegardez-le avant (voir plus bas).

```bash
docker compose --profile linux down -v
docker compose --profile linux pull
docker compose --profile linux up -d
```

L'installation repart de zéro : le compte `admin` est recréé avec son mot de
passe initial, qu'il faut changer à la première connexion.

### Remettre la base à zéro en gardant le certificat CA

Souvent préférable au `down -v` : on ne détruit que la base, le CA déployé sur
les postes reste valable.

```bash
docker compose --profile linux down
docker volume rm grand-duc_pgdata      # adapter le préfixe au nom du projet
docker compose --profile linux up -d
```

Le préfixe du volume est le nom du projet Compose, c'est-à-dire celui du
répertoire. `docker volume ls | grep pgdata` donne le nom exact.

### Sauvegardes

À faire avant toute opération destructive :

```bash
# Base de données
docker compose exec -T db pg_dump -U hibou grand_duc > grand-duc-$(date +%F).sql

# Certificat CA (clé privée incluse — à stocker en lieu sûr)
docker run --rm -v grand-duc_certs:/c -v "$PWD":/out alpine   tar czf /out/grand-duc-ca-$(date +%F).tar.gz -C /c .
```

Restauration de la base après un `down -v` :

```bash
cat grand-duc-2026-01-31.sql | docker compose exec -T db psql -U hibou -d grand_duc
```

### Revenir à une version antérieure

```bash
sed -i 's|^GRAND_DUC_VERSION=.*|GRAND_DUC_VERSION=0.1.5|' .env
docker compose --profile linux pull
docker compose --profile linux up -d
```

> ⚠️ Le retour arrière ne **défait pas** les migrations de base déjà appliquées.
> Une version antérieure peut refuser de démarrer sur un schéma plus récent.
> Restaurez une sauvegarde de la base prise avant la mise à jour si le backend
> ne démarre plus.

---

## Déploiement du certificat CA

Au premier lancement, le proxy génère une CA persistante (`grand-duc-ca.crt` / `grand-duc-ca.key`).
Ce certificat doit être déployé sur tous les postes clients pour le filtrage HTTPS.

**Windows (GPO recommandée) :**
```
certlm.msc → Autorités de certification racines de confiance → Importer
```

**Linux (Debian/Ubuntu) :**
```bash
cp grand-duc-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates
```

**Firefox (toutes plateformes) :**
Paramètres → Vie privée → Certificats → Importer

---

## Connexion à l'interface

- URL : `http://localhost` (Docker) ou `http://localhost:5173` (dev)
- Identifiants par défaut : `admin` / `admin`
- Le mot de passe doit être changé à la première connexion

---

## Gestion des règles de filtrage

Les règles sont des **expressions régulières Rust** évaluées par priorité.
Elles se gèrent depuis l'interface web ou directement en SQL :

```sql
-- Bloquer un domaine
INSERT INTO filter_rules (pattern, action, description, priority)
VALUES ('^https?://(www\.)?example\.com', 'block', 'Exemple', 50);

-- Désactiver temporairement
UPDATE filter_rules SET enabled = FALSE WHERE id = 3;
```

Le cache est rechargé automatiquement **toutes les 5 minutes**.

---

## Architecture du cache

```
Requête HTTP
     │
     ▼
is_blocked(url)
     │
     └── rules_cache.read().await   ← verrou partagé (non bloquant)
               │
               ├── itère les FilterRule par priorité
               └── retourne true dès le premier Block

Toutes les 5 min (tokio::spawn)
     │
     └── refresh_rules_cache()  → recharge depuis PostgreSQL
     └── refresh_client_cache() → recharge les groupes/IPs
     └── refresh_block_page()   → recharge le template de blocage

Toutes les 10s
     └── refresh_killswitch()   → vérifie l'état du killswitch
```

---

## Benchmark de performance

Tests effectues sur une connexion fibre 1 Gbps avec le proxy en interception TLS (MitM).
Deux tours de mesures, chacun avec 2x Speedtest (Ookla) et 2x Fast.com (Netflix).

### Resultats moyens — Speedtest (Ookla)

| Metrique | Avec proxy | Sans proxy | Impact |
|---|---|---|---|
| Download | 945 Mbps | 889 Mbps | ~0% (marge d'erreur) |
| Upload | 846 Mbps | 827 Mbps | ~0% (marge d'erreur) |

### Resultats moyens — Fast.com (Netflix)

| Metrique | Avec proxy | Sans proxy | Impact |
|---|---|---|---|
| Connexion | 902 Mbps | 942 Mbps | **-4.2%** |
| Latence (idle) | 12.75 ms | 3.25 ms | **+9.5 ms** |
| Latence (charge) | 25.75 ms | 19.75 ms | **+6 ms** |
| Upload | 795 Mbps | 860 Mbps | **-7.6%** |

### Analyse

**Debit** : la perte est de 4-7% sur le throughput, ce qui est remarquable pour un proxy MitM
qui intercepte, dechiffre et re-chiffre chaque connexion TLS. La plupart des proxys
d'entreprise (Squid, mitmproxy, Zscaler) introduisent 15-30% de perte dans des conditions
similaires.

**Latence** : +9.5 ms en idle, correspondant au cout du double handshake TLS
(client-proxy + proxy-serveur). Sur du trafic web classique, c'est imperceptible.
Pour le gaming ou le temps reel, le TLS bypass est recommande.

### Evaluation

| Critere | Note |
|---|---|
| Impact debit | Excellent (< 5% en download) |
| Impact latence | Bon (+10 ms, attendu pour un MitM TLS) |
| Capacite estimee | ~900 Mbps sature |
| Stabilite | Bonne (ecarts faibles entre les tours) |

Pour 30 postes a 100 Mbps chacun en pointe, le proxy peut theoriquement supporter ~9x la charge.
Meme avec 30 utilisateurs simultanes en streaming HD (25 Mbps chacun = 750 Mbps total),
il reste de la marge. Le bottleneck sera la connexion internet, pas le proxy.

![](https://dawn-wave-6f61.hack-h.workers.dev/?project=github%2Fgrand-duc-proxy)
