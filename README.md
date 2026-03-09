# Corp Proxy

Proxy HTTP/HTTPS d'entreprise (30 postes) — Pure Rust, zéro OpenSSL.

## Stack technique

| Rôle | Crate |
|---|---|
| Framework proxy | `hudsucker 0.21` (hyper 1.x) |
| TLS client/CA | `rustls` + `rcgen` (pure Rust) |
| Runtime async | `tokio 1` |
| Base de données | `sqlx 0.7` + PostgreSQL |
| Filtrage | `regex` compilé en cache |

---

## Prérequis

- **Rust** ≥ 1.75 stable (`rustup update stable`)
- **PostgreSQL** ≥ 14
- Aucun Perl, aucun OpenSSL system requis

---

## Installation

### 1. Base de données

```bash
createdb proxy_db
psql -U postgres -d proxy_db -f sql/init.sql
```

Créez un utilisateur dédié :
```sql
CREATE USER proxy_user WITH PASSWORD 'votre_mot_de_passe';
GRANT SELECT ON filter_rules TO proxy_user;
GRANT INSERT ON access_logs  TO proxy_user;
GRANT USAGE, SELECT ON SEQUENCE access_logs_id_seq TO proxy_user;
```

### 2. Variables d'environnement

```bash
export DATABASE_URL="postgresql://proxy_user:password@localhost/proxy_db"
export PROXY_ADDR="0.0.0.0:8080"   # optionnel
export RUST_LOG="corp_proxy=info"   # optionnel
```

### 3. Compilation et lancement

```bash
cargo build --release
./target/release/corp-proxy
```

---

## Déploiement du certificat CA (obligatoire pour HTTPS)

À chaque démarrage, le proxy génère une CA éphémère en mémoire.  
Pour la persistance, exportez le PEM via un endpoint ou modifiez `build_ca()`  
pour lire un fichier CA fixe.

**Windows (GPO recommandée) :**
```
certlm.msc → Autorités de certification racines de confiance → Importer
```

**Linux (Debian/Ubuntu) :**
```bash
cp corp-proxy-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates
```

**Firefox (toutes plateformes) :**  
Paramètres → Vie privée → Certificats → Importer

---

## Gestion des règles de filtrage

Les règles sont des **expressions régulières Rust** (`crate regex`) évaluées  
dans l'ordre croissant de `priority`. La **première correspondance l'emporte**.

```sql
-- Bloquer un nouveau domaine
INSERT INTO filter_rules (pattern, action, description, priority)
VALUES ('^https?://(www\.)?example\.com', 'block', 'Exemple', 50);

-- Désactiver temporairement une règle
UPDATE filter_rules SET enabled = FALSE WHERE id = 3;
```

Le cache est rechargé automatiquement **toutes les 5 minutes**.  
Pour un rechargement immédiat, redémarrez le processus.

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
               ├── itère les FilterRule dans l'ordre de priorité
               └── retourne true dès la première correspondance Block
                   (false si aucune règle ne matche → autoriser)

Toutes les 5 min (tokio::spawn)
     │
     └── refresh_rules_cache()
               ├── requête PostgreSQL
               ├── compile les Regex dans un Vec local
               └── rules_cache.write().await  ← verrou exclusif (bref)
                         └── *cache = new_rules  (swap atomique)
```