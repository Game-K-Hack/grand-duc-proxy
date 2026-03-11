# Grand-Duc — Proxy d'entreprise HTTP/HTTPS

## Vue d'ensemble

Grand-Duc est un proxy d'entreprise HTTP/HTTPS avec filtrage par regex, gestion des
utilisateurs par IP, groupes de clients, et interface d'administration web.

- **Proxy** : Rust — intercepte et filtre le trafic HTTP/HTTPS
- **Backend admin** : Python FastAPI — API REST pour gérer les règles et utilisateurs
- **Frontend admin** : Vue 3 — interface web d'administration

---

## Structure du projet

```
grand-duc/
├── src/
│   └── main.rs                        # Proxy Rust (point d'entrée unique)
├── Cargo.toml
├── grand-duc-ca.key                   # Clé privée CA (PKCS#8 DER) — NE PAS VERSIONNER
├── grand-duc-ca.crt                   # Certificat CA (PEM) — à distribuer aux postes
│
└── grand-duc-admin/
    ├── backend/
    │   ├── main.py                    # Point d'entrée FastAPI
    │   ├── config.py                  # Settings (pydantic-settings, lit .env)
    │   ├── database.py                # Engine SQLAlchemy async + get_db()
    │   ├── models.py                  # Modèles ORM SQLAlchemy
    │   ├── security.py                # bcrypt (direct, sans passlib), JWT HS256
    │   ├── .env                       # Variables d'environnement (NE PAS VERSIONNER)
    │   ├── requirements.txt
    │   └── routers/
    │       ├── __init__.py
    │       ├── auth.py                # POST /api/auth/login, GET /api/auth/me
    │       ├── rules.py               # CRUD /api/rules
    │       ├── logs.py                # GET /api/logs
    │       ├── stats.py               # GET /api/stats, GET /api/stats/traffic
    │       ├── users.py               # CRUD /api/users (comptes admin)
    │       ├── client_groups.py       # CRUD /api/client-groups + règles du groupe
    │       └── client_users.py        # CRUD /api/client-users + groupes + test-access
    │
    └── frontend/
        ├── package.json
        ├── vite.config.js             # Proxy /api → http://localhost:8000
        └── src/
            ├── main.js
            ├── App.vue                # Layout + sidebar navigation
            ├── assets/
            │   └── main.css           # Thème sombre, variables CSS
            ├── api/
            │   └── index.js           # Axios + intercepteurs JWT, helpers par domaine
            ├── stores/
            │   └── auth.js            # Pinia store : token, user, isAdmin, fetchMe()
            ├── router/
            │   └── index.js           # Vue Router avec guards auth/admin
            └── views/
                ├── Login.vue
                ├── Dashboard.vue      # Stats + graphique SVG trafic réseau
                ├── Rules.vue          # CRUD règles regex
                ├── Logs.vue           # Journal des accès paginé
                ├── ClientGroups.vue   # Groupes + assignation des règles
                ├── ClientUsers.vue    # Utilisateurs IP + assignation multi-groupes
                ├── TestAccess.vue     # Simulateur d'accès utilisateur/URL
                └── Users.vue          # Comptes administrateurs
```

---

## Base de données PostgreSQL

- **Serveur** : localhost
- **Base** : `grand_duc`
- **Utilisateur** : `hibou` / `root`
- **URL async** : `postgresql+asyncpg://hibou:root@localhost/grand_duc`

### Tables

#### `filter_rules` — Règles regex globales
```sql
id          BIGSERIAL PRIMARY KEY
pattern     TEXT NOT NULL              -- regex Python/Rust (re::Regex)
action      TEXT CHECK IN ('block','allow')
priority    INTEGER DEFAULT 100        -- plus petit = plus prioritaire
description TEXT
enabled     BOOLEAN DEFAULT TRUE
created_at  TIMESTAMPTZ DEFAULT NOW()
updated_at  TIMESTAMPTZ DEFAULT NOW()
```

#### `access_logs` — Journal des accès proxy
```sql
id          BIGSERIAL PRIMARY KEY
client_ip   TEXT                       -- IP source (peut être NULL sur anciens logs)
host        TEXT                       -- domaine (peut être NULL sur anciens logs)
url         TEXT
method      TEXT
blocked     BOOLEAN
user_agent  TEXT
accessed_at TIMESTAMPTZ DEFAULT NOW()
```

#### `users` — Comptes administrateurs de l'interface web
```sql
id              BIGSERIAL PRIMARY KEY
username        TEXT UNIQUE NOT NULL
email           TEXT
hashed_password TEXT NOT NULL          -- bcrypt hash (direct, sans passlib)
role            TEXT CHECK IN ('admin','viewer')
enabled         BOOLEAN DEFAULT TRUE
created_at      TIMESTAMPTZ DEFAULT NOW()
last_login      TIMESTAMPTZ
```
Compte initial : `admin` / `root` (à changer)

#### `client_groups` — Groupes de clients
```sql
id          BIGSERIAL PRIMARY KEY
name        TEXT UNIQUE NOT NULL
description TEXT
created_at  TIMESTAMPTZ DEFAULT NOW()
```

#### `client_users` — Utilisateurs identifiés par IP
```sql
id          BIGSERIAL PRIMARY KEY
ip_address  TEXT UNIQUE NOT NULL       -- ex: "192.168.1.42"
label       TEXT                       -- nom lisible, ex: "Poste Jean-Marie"
created_at  TIMESTAMPTZ DEFAULT NOW()
```
⚠️ Pas de `group_id` ici — relation many-to-many via `client_user_groups`

#### `client_user_groups` — Jonction utilisateurs ↔ groupes (many-to-many)
```sql
user_id     BIGINT REFERENCES client_users(id)  ON DELETE CASCADE
group_id    BIGINT REFERENCES client_groups(id) ON DELETE CASCADE
PRIMARY KEY (user_id, group_id)
```
Un utilisateur peut appartenir à plusieurs groupes simultanément.

#### `group_rules` — Règles actives dans un groupe
```sql
id         BIGSERIAL PRIMARY KEY
group_id   BIGINT REFERENCES client_groups(id) ON DELETE CASCADE
rule_id    BIGINT REFERENCES filter_rules(id)  ON DELETE CASCADE
action     TEXT CHECK IN ('block','allow')      -- peut différer de l'action globale
created_at TIMESTAMPTZ DEFAULT NOW()
UNIQUE (group_id, rule_id)
```
Permet à un groupe d'activer une règle avec une action différente de la globale.
Ex : règle globale `block youtube.com` → groupe "Directeurs" l'active en `allow`.

---

## Proxy Rust (`src/main.rs`)

### Dépendances Cargo.toml
```toml
hudsucker    = { version = "0.21", default-features = false, features = ["rcgen-ca","rustls-client"] }
tokio        = { version = "1", features = ["full"] }
sqlx         = { version = "0.7", features = ["runtime-tokio-rustls","postgres"] }
rcgen        = "0.13"
regex        = "1"
tracing      = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
anyhow       = "1"
base64       = "0.22"
[target.'cfg(windows)'.dependencies]
windows-sys  = { version = "0.52", features = ["Win32_System_Console"] }
```

### Structs principales
- `FilterAction` : enum `Block` / `Allow`
- `FilterRule` : `{ id: i64, pattern: Regex, action: FilterAction }`
- `FilterRuleRow` : `sqlx::FromRow` pour lecture DB
- `ClientProfile` : `{ client_user_id: i64, group_id: Option<i64> }` — supprimé en v4, remplacé par :
- `ClientCache` : `{ ip_to_profile: HashMap<String, ClientProfile>, group_rules: HashMap<i64, Vec<(i64, FilterAction)>> }`
  - clé group_rules : group_id → liste de (rule_id, action)
- `AppState` : `{ db_pool: PgPool, rules_cache: Arc<RwLock<Vec<FilterRule>>>, client_cache: Arc<RwLock<ClientCache>> }`
- `ProxyHandler` : implémente `HttpHandler` de hudsucker

### Logique de filtrage (`is_blocked(client_ip, url)`)
```
Pour chaque règle (triées par priorité croissante) :
  Si règle.pattern match url :
    1. L'IP est-elle connue dans client_cache ?
       → Récupère ses group_ids
       → Pour chaque groupe, cherche si cette règle est dans group_rules
       → Si oui : applique l'action du groupe (priorité groupe)
    2. Sinon : applique l'action globale de la règle
    → RETURN résultat
Aucune règle ne correspond → RETURN false (autorisé)
```

### CA persistante
- `grand-duc-ca.key` : clé privée PKCS#8 DER (générée au premier lancement)
- `grand-duc-ca.crt` : certificat X.509 PEM (à installer sur les postes clients)
- Rechargement automatique si les fichiers existent

### Variables d'environnement proxy
```
DATABASE_URL=postgresql://hibou:root@localhost/grand_duc
PROXY_ADDR=0.0.0.0:8080
RUST_LOG=grand_duc=info
```
⚠️ Le proxy utilise `postgresql://` (sqlx sync-style), pas `postgresql+asyncpg://`

### Hôte admin
`ADMIN_HOST = "grand-duc.proxy"` — requêtes vers ce domaine servent l'interface admin

### Rafraîchissement des caches
Toutes les 5 minutes via `tokio::spawn` :
1. `refresh_rules_cache()` — recharge `filter_rules` depuis DB
2. `refresh_client_cache()` — recharge `client_users`, `client_user_groups`, `group_rules`

---

## Backend Python

### Démarrage
```cmd
# Depuis grand-duc-admin/backend/
# Python 3.12 OBLIGATOIRE (Python 3.14 incompatible avec asyncpg + pydantic-core)
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

### config.py
```python
class Settings(BaseSettings):
    DATABASE_URL:                str = "postgresql+asyncpg://hibou:root@localhost/grand_duc"
    SECRET_KEY:                  str = "..."
    ALGORITHM:                   str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ADMIN_CORS_ORIGIN:           str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```
⚠️ Les variables d'environnement système ont priorité sur `.env` —
si `DATABASE_URL` est définie au niveau Windows, elle écrase le `.env`.

### security.py
```python
import bcrypt
# PAS de passlib — incompatible avec bcrypt 4.x

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

### Authentification
- JWT HS256 via `python-jose`
- `get_current_user` : vérifie token + `user.enabled`
- `require_admin` : vérifie `role == 'admin'`
- Viewer : lecture seule (rules, logs, stats, client-groups, client-users)
- Admin : CRUD complet + users + modifications groupes/règles

### Endpoints REST

#### Auth
```
POST /api/auth/login     OAuth2PasswordRequestForm → { access_token, token_type }
GET  /api/auth/me        → User courant
```

#### Règles globales
```
GET    /api/rules?skip=&limit=&search=    → { items, total }
POST   /api/rules                          → FilterRule
PUT    /api/rules/{id}                     → FilterRule
PATCH  /api/rules/{id}/toggle              → { enabled }
DELETE /api/rules/{id}
```

#### Logs
```
GET /api/logs?skip=&limit=&search=&blocked=    → { items, total }
```
⚠️ `host` peut être NULL sur les anciens logs — modèle Pydantic utilise `Optional[str]`

#### Stats
```
GET /api/stats                      → StatsResponse
GET /api/stats/traffic?mode=24h|1h  → { points: [{ label, total, blocked, allowed }], mode }
```
`mode=24h` : 24 points par heure via `generate_series` PostgreSQL
`mode=1h`  : 60 points par minute

#### Groupes clients
```
GET    /api/client-groups                           → list[GroupOut]
POST   /api/client-groups                           → GroupOut
PUT    /api/client-groups/{id}                      → GroupOut
DELETE /api/client-groups/{id}
GET    /api/client-groups/{id}/rules                → list[GroupRuleOut]
POST   /api/client-groups/{id}/rules                → GroupRuleOut  (upsert)
DELETE /api/client-groups/{id}/rules/{rule_id}
```
`GroupOut` inclut `member_count` et `rule_count`
`GroupRuleOut` inclut `global_action` (action de la règle globale) et `action` (action dans ce groupe)

#### Utilisateurs clients
```
GET    /api/client-users                            → list[ClientUserOut]
POST   /api/client-users                            → ClientUserOut
PUT    /api/client-users/{id}                       → ClientUserOut  (label seulement)
DELETE /api/client-users/{id}
GET    /api/client-users/{id}/groups                → list[GroupBrief]
PUT    /api/client-users/{id}/groups                → list[GroupBrief]  (remplace tout)
POST   /api/client-users/test-access                → TestAccessOut
```
`ClientUserOut` inclut `groups: list[{ id, name }]`
`SetGroupsIn` : `{ group_ids: list[int] }` — remplace entièrement la liste

#### Test d'accès
```
POST /api/client-users/test-access
Body : { user_id: int, url: str }
→ {
    url, blocked,
    reason: { rule_id, pattern, action, group_id, group_name, source } | null,
    user_ip, user_label,
    groups: list[str]
  }
```
`source` : `"group"` si une group_rule a déclenché, `"global"` si règle globale

#### Comptes admin
```
GET    /api/users
POST   /api/users
PUT    /api/users/{id}
DELETE /api/users/{id}
```

---

## Frontend Vue 3

### Démarrage
```cmd
# Depuis grand-duc-admin/frontend/
npm run dev    # http://localhost:5173
```

### Variables CSS (main.css)
```css
--bg, --surface, --surface2   /* fonds sombre */
--border                       /* bordures */
--text, --text-muted           /* textes */
--accent                       /* violet #8b5cf6 */
--blue   #58a6ff
--green  #3fb950
--red    #f85149
```

### Classes CSS utilitaires disponibles
```
.card              /* conteneur avec fond surface + bordure + border-radius */
.card-title        /* titre de section */
.page-header       /* flex header avec titre + bouton */
.page-title
.stat-grid         /* grille 3 col responsive pour les stat-cards */
.stat-card / .stat-label / .stat-value
.stat-value.blue / .red / .green / .accent
.table-wrap        /* conteneur table avec overflow */
table > thead > tr > th / td
.badge / .badge-block / .badge-allow
.btn / .btn-primary / .btn-ghost / .btn-danger / .btn-sm / .btn-icon
.form-input / .form-select / .form-label / .form-group
.modal-overlay / .modal / .modal-title / .modal-footer
.alert / .alert-error
.nav-item / .nav-item.active / .nav-section
.mono              /* font-family monospace */
```

### stores/auth.js (Pinia)
```javascript
// State : token, user { username, role }
// Getters : isLoggedIn, isAdmin
// Actions : login(username, password), logout(), fetchMe()
```

### api/index.js — helpers disponibles
```javascript
authApi        : { login, me }
rulesApi       : { list(params), create, update, toggle, delete }
logsApi        : { list(params) }
statsApi       : { get(), traffic(mode) }
usersApi       : { list, create, update, delete }
groupsApi      : { list, create, update, delete, listRules, addRule, deleteRule }
clientUsersApi : { list, create, update, delete, getGroups, setGroups, testAccess }
```
⚠️ `rulesApi.list()` retourne `{ items, total }` (pas un tableau direct)
⚠️ `groupsApi.listRules(id)` retourne un tableau de `GroupRuleOut`

### Comportement des toggles (ClientGroups.vue)
Quand on active une règle pour un groupe, l'action par défaut assignée est
**l'inverse de l'action globale** (ex : règle globale=block → groupe active en allow).
L'action peut ensuite être changée via un `<select>` inline dans la même ligne.

### Graphique trafic (Dashboard.vue)
SVG natif, pas de librairie externe. Dimensions : `W=900, H=220`.
`yTicks` calculé dynamiquement avec max 6 graduations "propres" (nice numbers).
Auto-refresh toutes les 30s via `setInterval` + `onUnmounted` cleanup.

### Routes
```
/               Dashboard     (tous)
/rules          Règles        (tous)
/logs           Logs          (tous)
/client-groups  Groupes       (admin)
/client-users   Utilisateurs  (admin)
/test-access    Test d'accès  (admin)
/users          Comptes admin (admin)
/login          Login         (public)
```

---

## Conventions de code

### Python
- SQLAlchemy 2.0 async — toujours `await db.execute(select(...))` puis `.scalars().all()` ou `.scalar_one_or_none()`
- Upsert pattern : `select → if existing: update else: insert`
- Les routers retournent toujours des modèles Pydantic typés (`response_model=`)
- `Optional[str]` pour tous les champs nullable (host, label, description…)

### Vue.js
- Composition API (`<script setup>`) — pas d'Options API
- `ref()` pour l'état local, `computed()` pour les dérivés
- Chargement en parallèle avec `Promise.all([...])` quand possible
- Sauvegardes inline sans bouton global (ex: toggle → requête immédiate)
- Pas de framework UI (Vuetify, PrimeVue…) — CSS custom uniquement

### Rust
- Pas de `delay()` / `thread::sleep()` — utiliser `tokio::time`
- Caches en `Arc<RwLock<...>>` — `read().await` pour lecture, `write().await` pour écriture
- Logging via `tracing` (`info!`, `error!`, `warn!`)
- Fire-and-forget pour les logs : `tokio::spawn(async move { ... })`

---

## Points d'attention / pièges connus

1. **Python 3.12 obligatoire** — 3.13+ incompatible avec asyncpg et pydantic-core
2. **passlib supprimé** — utiliser `bcrypt` directement (passlib incompatible avec bcrypt 4.x)
3. **Variable DATABASE_URL** — les variables Windows ont priorité sur `.env`
4. **host NULL dans access_logs** — colonne ajoutée en v3, anciens logs ont NULL → `Optional[str]`
5. **Proxy Rust** utilise `postgresql://` (pas `+asyncpg`) dans DATABASE_URL
6. **rulesApi.list()** retourne `{ items, total }` — accéder via `.data.items`
7. **setGroups** remplace entièrement les groupes — envoyer la liste complète des group_ids
8. **generate_series** PostgreSQL pour le graphique trafic — nécessite PostgreSQL 9.4+
9. **CA persistante** — `grand-duc-ca.key` et `.crt` générés au premier lancement Rust