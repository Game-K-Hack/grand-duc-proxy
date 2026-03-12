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
├── templates/
│   └── blocked/
│       └── index.html                 # Page de blocage par défaut (HTML + assets base64)
├── grand-duc-ca.key                   # Clé privée CA (PKCS#8 DER) — NE PAS VERSIONNER
├── grand-duc-ca.crt                   # Certificat CA (PEM) — à distribuer aux postes
│
└── grand-duc-admin/
    ├── backend/
    │   ├── main.py                    # Point d'entrée FastAPI + seeding rôles builtin
    │   ├── config.py                  # Settings (pydantic-settings, lit .env)
    │   ├── database.py                # Engine SQLAlchemy async + get_db()
    │   ├── models.py                  # Modèles ORM SQLAlchemy (User, Role, AppSetting…)
    │   ├── security.py                # JWT HS256, require_permission(), require_admin
    │   ├── permissions.py             # ALL_PERMISSIONS (31 clés), labels FR, rôles builtin
    │   ├── .env                       # Variables d'environnement (NE PAS VERSIONNER)
    │   ├── requirements.txt
    │   ├── services/
    │   │   └── email.py               # Envoi e-mails, template HTML, render_template()
    │   └── routers/
    │       ├── __init__.py
    │       ├── auth.py                # POST /api/auth/login, GET /api/auth/me (+ permissions)
    │       ├── rules.py               # CRUD /api/rules
    │       ├── logs.py                # GET /api/logs
    │       ├── stats.py               # GET /api/stats, GET /api/stats/traffic
    │       ├── users.py               # CRUD /api/users (comptes admin, role_id)
    │       ├── roles.py               # CRUD /api/roles + GET /api/roles/permissions
    │       ├── client_groups.py       # CRUD /api/client-groups + règles du groupe
    │       ├── client_users.py        # CRUD /api/client-users + groupes + test-access
    │       ├── tls_bypass.py          # CRUD /api/tls-bypass (exceptions TLS)
    │       ├── killswitch.py          # GET/POST /api/killswitch + historique
    │       ├── certificates.py        # Gestion CA : génération, import, historique
    │       ├── proxy_control.py       # Statut/redémarrage proxy + logs SSE
    │       ├── integrations.py        # CRUD /api/integrations (RMM) + sync
    │       └── settings.py            # SMTP, notifications, templates, thème, page de blocage
    │
    └── frontend/
        ├── package.json
        ├── vite.config.js             # Proxy /api → http://localhost:8000
        └── src/
            ├── main.js
            ├── App.vue                # Layout + sidebar navigation (permission-aware)
            ├── assets/
            │   └── main.css           # Variables CSS, classes utilitaires
            ├── api/
            │   └── index.js           # Axios + intercepteurs JWT, cache, helpers par domaine
            ├── composables/
            │   └── useTheme.js        # Thèmes prédéfinis, couleurs custom, persistance
            ├── stores/
            │   └── auth.js            # Pinia store : token, user, permissions, hasPermission()
            ├── router/
            │   └── index.js           # Vue Router avec guards par permissions
            └── views/
                ├── Login.vue
                ├── Dashboard.vue      # Stats + graphique SVG trafic réseau
                ├── Rules.vue          # CRUD règles regex
                ├── Logs.vue           # Journal des accès paginé
                ├── ClientGroups.vue   # Groupes + assignation des règles
                ├── ClientUsers.vue    # Utilisateurs IP + assignation multi-groupes
                ├── TestAccess.vue     # Simulateur d'accès utilisateur/URL
                ├── Users.vue          # Comptes administrateurs (role_id dynamique)
                ├── Roles.vue          # Gestion des rôles + permissions granulaires
                ├── TlsBypass.vue      # Exceptions TLS
                ├── Killswitch.vue     # Interrupteur d'urgence
                ├── Certificates.vue   # Certificats CA (génération, import, historique)
                ├── ProxyLogs.vue      # Logs proxy temps réel (SSE)
                ├── Settings.vue       # SMTP, notifications, templates, apparence, RMM
                └── Documentation.vue  # Guide intégré avec sommaire interactif
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

#### `roles` — Rôles et permissions
```sql
id          BIGSERIAL PRIMARY KEY
name        TEXT UNIQUE NOT NULL
description TEXT
permissions TEXT NOT NULL DEFAULT '{}'  -- JSON {"perm.key": true}
is_builtin  BOOLEAN NOT NULL DEFAULT FALSE
created_at  TIMESTAMPTZ DEFAULT NOW()
```
Rôles builtin : `Administrateur` (toutes permissions), `Lecteur` (*.read)

#### `users` — Comptes administrateurs de l'interface web
```sql
id              BIGSERIAL PRIMARY KEY
username        TEXT UNIQUE NOT NULL
email           TEXT
hashed_password TEXT NOT NULL          -- bcrypt hash
role_id         BIGINT REFERENCES roles(id)
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
action     TEXT CHECK IN ('block','allow')      -- stocké en DB mais IGNORÉ par le proxy
created_at TIMESTAMPTZ DEFAULT NOW()
UNIQUE (group_id, rule_id)
```
⚠️ **Modèle simplifié** : La colonne `action` de `group_rules` est présente en DB mais **ignorée**.
L'action vient toujours de `filter_rules.action`. Un groupe active/désactive simplement une règle.
L'interface admin (ClientGroups.vue) envoie `action = rule.action` lors de l'activation — sans
permettre à l'utilisateur de choisir une action différente.

#### `tls_bypass` — Exceptions TLS
```sql
id          BIGSERIAL PRIMARY KEY
host        TEXT UNIQUE NOT NULL       -- ex: "discord.com"
description TEXT
created_at  TIMESTAMPTZ DEFAULT NOW()
```

#### `killswitch` — État et historique du killswitch
```sql
id          BIGSERIAL PRIMARY KEY
active      BOOLEAN NOT NULL
changed_by  TEXT
changed_at  TIMESTAMPTZ DEFAULT NOW()
```

#### `smtp_config` — Configuration SMTP (table `app_settings`, clé unique)
#### `app_settings` — Paramètres globaux (clé-valeur)
```sql
key         TEXT PRIMARY KEY           -- ex: "smtp_config", "email_template", "block_page_template"
value       TEXT NOT NULL              -- JSON ou HTML selon la clé
```

#### `notification_prefs` — Préférences de notification par utilisateur
```sql
user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE
event_type  TEXT NOT NULL              -- ex: "certificate", "proxy_restart", "killswitch"
enabled     BOOLEAN DEFAULT FALSE
PRIMARY KEY (user_id, event_type)
```

#### `user_themes` — Thème par utilisateur
```sql
user_id     BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
theme       TEXT NOT NULL              -- JSON {presetId, customColors}
```

#### `rmm_integrations` — Intégrations RMM
```sql
id                    BIGSERIAL PRIMARY KEY
name                  TEXT NOT NULL
type                  TEXT NOT NULL              -- tactical, ninja, datto, atera
url                   TEXT NOT NULL
api_key               TEXT NOT NULL
api_secret            TEXT
sync_interval_minutes INTEGER DEFAULT 60
auto_group_by         TEXT DEFAULT 'none'        -- none, client, site, client_site
enabled               BOOLEAN DEFAULT TRUE
last_sync_at          TIMESTAMPTZ
last_sync_status      TEXT
created_at            TIMESTAMPTZ DEFAULT NOW()
```

#### `certificate_history` — Historique des certificats CA
```sql
id          BIGSERIAL PRIMARY KEY
action      TEXT NOT NULL              -- "generate" ou "import"
fingerprint TEXT
changed_by  TEXT
created_at  TIMESTAMPTZ DEFAULT NOW()
```

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
- `ClientCache` :
  - `ip_to_user_id: HashMap<String, i64>` — IP → client_user_id
  - `user_groups: HashMap<i64, Vec<i64>>` — client_user_id → liste de group_ids
  - `group_rules: HashMap<i64, HashSet<i64>>` — group_id → ensemble de rule_ids actifs
  - `default_group_id: Option<i64>` — ID du groupe par défaut
  - `default_group_rules: HashSet<i64>` — rule_ids du groupe par défaut
- `AppState` : `{ db_pool: PgPool, rules_cache: Arc<RwLock<Vec<FilterRule>>>, client_cache: Arc<RwLock<ClientCache>> }`
- `ProxyHandler` : implémente `HttpHandler` de hudsucker

### Logique de filtrage (`is_blocked(client_ip, url)`)
```
Niveau 1 — Groupes explicites (utilisateur connu avec au moins 1 groupe) :
  Pour chaque règle (triées par priorité croissante) :
    Si règle.pattern match url :
      Pour chaque groupe de l'utilisateur :
        Si groupe possède cette règle :
          Si règle.action == Allow → RETURN false (allow wins immédiatement)
          Sinon → found_block = true (continue à chercher un allow)
  RETURN found_block

Niveau 2 — Groupe par défaut (IP inconnue ou utilisateur sans groupe) :
  Première règle matching ET dans default_group_rules → applique son action

Niveau 3 — Règle globale directe (si pas de groupe par défaut configuré) :
  Première règle matching → applique son action

Aucune règle ne correspond → RETURN false (autorisé par défaut)
```

### CONNECT (tunnels HTTPS)
Les requêtes CONNECT sont logguées en DB (`method="CONNECT"`, `blocked=false`) pour
visualiser tout le trafic, y compris les apps qui échouent au niveau TLS sans générer
de requête HTTP. Le filtrage effectif se fait sur les requêtes HTTP décryptées.

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
- `verify_password` / `hash_password` via `passlib` + bcrypt
- `get_current_user` : vérifie JWT + `user.enabled`, charge les permissions du rôle en cache
- `require_permission(*keys)` : factory de dépendance FastAPI, vérifie les permissions granulaires
- `require_permission_query(*keys)` : variante pour SSE (token en query param)
- `require_admin` : alias legacy, vérifie `role == 'admin'`

### permissions.py (31 permissions)
Convention : `<section>.<action>` (read | write | use | restart)

| Section | Permissions |
|---------|-------------|
| Monitoring | `dashboard.read`, `logs.read`, `proxy_logs.read` |
| Filtrage | `rules.read/write`, `client_groups.read/write`, `client_users.read/write`, `test_access.use` |
| Administration | `tls_bypass.read/write`, `killswitch.read/write`, `certificates.read/write`, `users.read/write`, `roles.read/write`, `proxy.restart` |
| Paramètres | `settings.smtp.read/write`, `settings.templates.read/write`, `settings.appearance.read/write`, `settings.rmm.read/write` |

### Authentification
- JWT HS256 via `python-jose`
- `get_current_user` : vérifie token + `user.enabled` + JOIN avec Role pour charger permissions
- Permissions granulaires par endpoint via `require_permission("perm.key")`
- `/api/auth/me` retourne `permissions: dict` et `role_name: str`

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

#### Rôles
```
GET    /api/roles/permissions              → liste des 31 permissions avec labels FR
GET    /api/roles                          → list[RoleOut]
POST   /api/roles                          → RoleOut
PUT    /api/roles/{id}                     → RoleOut  (builtin : permissions modifiables, nom/suppression interdits)
DELETE /api/roles/{id}                     (interdit sur les rôles builtin)
```

#### Exceptions TLS
```
GET    /api/tls-bypass                     → list[TlsBypassOut]
POST   /api/tls-bypass                     → TlsBypassOut
DELETE /api/tls-bypass/{id}
```

#### Killswitch
```
GET    /api/killswitch                     → { active, changed_by, changed_at }
POST   /api/killswitch                     → { active }  (body : { active: bool })
GET    /api/killswitch/history             → list (50 dernières entrées)
POST   /api/killswitch/verify-password     → { valid: bool }
```

#### Certificats CA
```
GET    /api/certificates/info              → { fingerprint, issuer, not_before, not_after, … }
GET    /api/certificates/ca.crt            → téléchargement PEM (public, sans auth)
POST   /api/certificates/generate          → génère nouveau CA (key + cert)
POST   /api/certificates/import            → import fichiers key + cert (multipart)
GET    /api/certificates/history           → list (50 dernières entrées)
```

#### Contrôle proxy
```
GET    /api/proxy/status                   → { running, pid, uptime }
GET    /api/proxy/logs                     → SSE (token en query param, permission proxy_logs.read)
POST   /api/proxy/restart                  → { ok }
```

#### Intégrations RMM
```
GET    /api/integrations                   → list[IntegrationOut]
POST   /api/integrations                   → IntegrationOut
PUT    /api/integrations/{id}              → IntegrationOut
DELETE /api/integrations/{id}
POST   /api/integrations/{id}/sync         → déclenche sync manuelle
```

#### Paramètres — SMTP
```
GET    /api/settings/smtp                  → SmtpConfigOut (password masqué)
PUT    /api/settings/smtp                  → { ok }
POST   /api/settings/smtp/test             → { ok }  (envoie un e-mail de test)
```

#### Paramètres — Templates
```
GET    /api/settings/email-template        → { template, is_custom }
PUT    /api/settings/email-template        → { ok }
DELETE /api/settings/email-template        → { ok }  (reset au défaut)
POST   /api/settings/email-template/preview → { html }

GET    /api/settings/block-page            → { template, is_custom }
PUT    /api/settings/block-page            → { ok }  (écrit aussi sur disque pour le proxy Rust)
DELETE /api/settings/block-page            → { ok }  (reset au défaut)
POST   /api/settings/block-page/preview    → { html }
```

#### Paramètres — Notifications (par utilisateur, pas de permission spéciale)
```
GET    /api/settings/notifications                → list[EventPref]
PUT    /api/settings/notifications                → { ok }
GET    /api/settings/notifications/rules          → list[RuleWatchOut]  (règles surveillées)
GET    /api/settings/notifications/rules/available → list[RuleWatchOut]
PUT    /api/settings/notifications/rules          → { ok }
```

#### Paramètres — Thème (par utilisateur, pas de permission spéciale)
```
GET    /api/settings/theme                 → { theme }  (JSON ou null)
PUT    /api/settings/theme                 → { ok }
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
// State : token, user { username, role_name, permissions }
// Getters : isLoggedIn, isAdmin
// Methods : login(username, password), logout(), fetchMe()
//           hasPermission(key), hasAnyPermission(...keys)
```

### api/index.js — helpers disponibles
```javascript
authApi         : { login, me }
rulesApi        : { list(params), create, update, toggle, delete }
logsApi         : { list(params) }
statsApi        : { get(), traffic(mode) }
usersApi        : { list, create, update, delete }
groupsApi       : { list, create, update, delete, listRules, addRule, deleteRule }
clientUsersApi  : { list, create, update, delete, getGroups, setGroups, testAccess }
tlsBypassApi    : { list, create, delete }
killswitchApi   : { get, set, history, verifyPassword }
certificatesApi : { info, generate, importCert, history, downloadUrl }
proxyApi        : { status, restart, logsUrl(token) }
settingsApi     : { getSmtp, updateSmtp, testSmtp,
                    getTemplate, setTemplate, resetTemplate, previewTemplate,
                    getBlockPage, setBlockPage, resetBlockPage, previewBlockPage,
                    getNotifications, setNotifications,
                    getRuleWatches, getAvailableRules, setRuleWatches,
                    getTheme, setTheme }
integrationsApi : { list, create, update, delete, sync }
rolesApi        : { list, permissions, create, update, delete }
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

### composables/useTheme.js
Gère les thèmes (presets prédéfinis + couleurs custom). Persiste côté serveur via `settingsApi`.
Variables CSS modifiées dynamiquement : `--bg`, `--surface`, `--surface2`, `--border`, `--text`,
`--text-muted`, `--accent`. Appliqué sur `document.documentElement.style`.

### Routes (permission-based guards)
```
/login           Login          (public)
/                Dashboard      (dashboard.read)
/rules           Règles         (rules.read)
/logs            Logs           (logs.read)
/client-groups   Groupes        (client_groups.read)
/client-users    Utilisateurs   (client_users.read)
/test-access     Test d'accès   (test_access.use)
/users           Comptes admin  (users.read)
/roles           Rôles          (roles.read)
/tls-bypass      Exceptions TLS (tls_bypass.read)
/killswitch      Killswitch     (killswitch.read)
/certificates    Certificats    (certificates.read)
/proxy-logs      Logs proxy SSE (proxy_logs.read)
/settings        Paramètres     (aucune — onglets filtrés par permissions)
/documentation   Documentation  (aucune)
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
10. **Rôles builtin** — `Administrateur` et `Lecteur` sont re-seedés au démarrage du backend ; ne pas les supprimer en DB
11. **Permissions dynamiques** — `ADMIN_PERMISSIONS` / `VIEWER_PERMISSIONS` sont générés depuis `ALL_PERMISSIONS`, ajouter une permission la propage automatiquement
12. **Page de blocage** — stockée en DB (`app_settings.block_page_template`) ET écrite sur disque (`PROXY_WORK_DIR/templates/blocked/index.html`) pour le proxy Rust
13. **SSE proxy logs** — utilise `require_permission_query` (token en query param, pas header Authorization)
14. **Thème / Notifications** — données personnelles par utilisateur, pas de permission spéciale requise (juste authentification)