//! Grand-Duc — Proxy HTTP/HTTPS d'entreprise
//!
//! Architecture :
//!   ┌──────────┐  HTTP/HTTPS   ┌───────────────┐   filtrage Regex    ┌──────────┐
//!   │  Client  │ ────────────► │  ProxyHandler │ ──(RwLock cache)──► │ Internet │
//!   └──────────┘               └───────┬───────┘                     └──────────┘
//!                                      │ async (fire-and-forget)
//!                                      ▼
//!                              ┌───────────────┐
//!                              │   PostgreSQL  │ (access_logs + filter_rules)
//!                              └───────────────┘
//!
//! Variables d'environnement :
//!   DATABASE_URL_PROXY  postgresql://user:pass@host/db   (requis)
//!   PROXY_ADDR    0.0.0.0:8080                           (optionnel, défaut : 0.0.0.0:8080)
//!
//! Interface d'administration :
//!   Configurer le proxy navigateur sur 127.0.0.1:8080, puis visiter http://grand-duc.proxy/

use std::{net::SocketAddr, path::PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use std::path::Path;
use std::collections::{HashMap, HashSet};

use anyhow::{anyhow, Result};
use hudsucker::{
    async_trait::async_trait,
    certificate_authority::RcgenAuthority,
    hyper::{header, Body, Request, Response, StatusCode},
    HttpContext, HttpHandler, ProxyBuilder, RequestOrResponse,
};
use mime_guess::from_path;
use rcgen::{BasicConstraints, CertificateParams, IsCa, KeyPair};
use regex::Regex;
use sqlx::PgPool;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

// ── Assets statiques ─────────────────────────────────────────────────────────

/// Hôte virtuel exposant l'interface d'administration.
/// Configurer le proxy sur 127.0.0.1:8080, puis ouvrir http://grand-duc.proxy/
const ADMIN_HOST: &str = "grand-duc.proxy";

// ─────────────────────────────────────────────────────────────────────────────
// Types métier
// ─────────────────────────────────────────────────────────────────────────────

/// Action associée à une règle de filtrage.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FilterAction {
    Block,
    Allow,
}

/// Règle de filtrage : pattern Regex compilé + action associée.
/// Le champ `compiled` est pré-calculé une seule fois au chargement.
#[derive(Debug, Clone)]
pub struct FilterRule {
    pub id:          i64,
    pub pattern:     String,
    pub compiled:    Regex,
    pub action:      FilterAction,
    pub description: Option<String>,
}

impl FilterRule {
    /// Tente de construire une règle en compilant le pattern Regex.
    /// Retourne `Err` si le pattern est syntaxiquement invalide.
    pub fn try_new(
        id:          i64,
        pattern:     &str,
        action:      FilterAction,
        description: Option<String>,
    ) -> Result<Self> {
        let compiled = Regex::new(pattern)
            .map_err(|e| anyhow!("Regex invalide pour la règle id={} '{}': {}", id, pattern, e))?;
        Ok(Self { id, pattern: pattern.to_owned(), compiled, action, description })
    }

    #[inline]
    pub fn matches(&self, url: &str) -> bool {
        self.compiled.is_match(url)
    }
}

/// Cache de tous les clients et leurs overrides de groupe.
/// Rechargé périodiquement depuis PostgreSQL.
#[derive(Debug, Default)]
pub struct ClientCache {
    /// IP → client_user_id
    pub ip_to_user_id:      HashMap<String, i64>,
    /// client_user_id → liste de group_ids
    pub user_groups:        HashMap<i64, Vec<i64>>,
    /// group_id → ensemble des rule_ids actifs dans ce groupe
    /// L'action vient toujours de FilterRule.action (définie sur la règle globale)
    pub group_rules:        HashMap<i64, HashSet<i64>>,
    /// ID du groupe par défaut
    pub default_group_id:   Option<i64>,
    /// rule_ids actifs dans le groupe par défaut
    pub default_group_rules: HashSet<i64>,
    /// Hôtes exemptés du filtrage (trafic toujours autorisé, sous-domaines inclus)
    pub tls_bypass:          HashSet<String>,
}

// ── Ligne brute lue depuis PostgreSQL ────────────────────────────────────────

#[derive(sqlx::FromRow)]
struct FilterRuleRow {
    id:          i64,
    pattern:     String,
    action:      String,
    description: Option<String>,
}

#[derive(sqlx::FromRow)]
struct ClientUserRow {
    id:         i64,
    ip_address: String,
}

#[derive(sqlx::FromRow)]
struct ClientUserGroupRow {
    user_id:  i64,
    group_id: i64,
}

#[derive(sqlx::FromRow)]
struct GroupRuleRow {
    group_id: i64,
    rule_id:  i64,
}

#[derive(sqlx::FromRow)]
struct DefaultGroupRow {
    id: i64,
}

#[derive(sqlx::FromRow)]
struct TlsBypassRow {
    host: String,
}

// ─────────────────────────────────────────────────────────────────────────────
// État partagé de l'application
// ─────────────────────────────────────────────────────────────────────────────

/// State clonable (Arc interne) partagé entre toutes les instances du handler.
#[derive(Clone)]
pub struct AppState {
    pub db_pool:     PgPool,
    /// Cache en mémoire des règles actives.
    /// Lecture très fréquente (chaque requête) → RwLock<Vec<…>>.
    /// Écriture rare (toutes les N minutes) → accès exclusif bref.
    pub rules_cache:  Arc<RwLock<Vec<FilterRule>>>,
    pub client_cache: Arc<RwLock<ClientCache>>,
    /// Killswitch : si true, tout le trafic est autorisé sans filtrage.
    /// Vérifié à chaque requête (AtomicBool = lock-free), mis à jour toutes les 10s.
    pub killswitch:   Arc<AtomicBool>,
}

impl AppState {
    /// Initialise le state : connexion PostgreSQL + premier chargement du cache.
    pub async fn new(database_url: &str) -> Result<Self> {
        // Force UTF-8 pour éviter le panic sur les messages d'erreur PostgreSQL en WIN1252
        let sep = if database_url.contains('?') { '&' } else { '?' };
        let url_utf8 = format!("{}{}options=-c%20client_encoding%3DUTF8", database_url, sep);
        let db_pool = PgPool::connect(&url_utf8).await?;
        let state = Self {
            db_pool,
            rules_cache:  Arc::new(RwLock::new(Vec::new())),
            client_cache: Arc::new(RwLock::new(ClientCache::default())),
            killswitch:   Arc::new(AtomicBool::new(false)),
        };
        state.refresh_rules_cache().await?;
        state.refresh_client_cache().await?;
        state.refresh_killswitch().await?;
        Ok(state)
    }

    // ── Gestion du cache ─────────────────────────────────────────────────────

    /// Recharge toutes les règles actives depuis PostgreSQL
    /// et remplace atomiquement le contenu du cache.
    pub async fn refresh_rules_cache(&self) -> Result<()> {
        let rows = sqlx::query_as::<_, FilterRuleRow>(
            r#"
            SELECT id, pattern, action, description
              FROM filter_rules
             WHERE enabled = TRUE
             ORDER BY priority DESC
            "#,
        )
        .fetch_all(&self.db_pool)
        .await?;

        let mut new_rules: Vec<FilterRule> = Vec::with_capacity(rows.len());
        for row in rows {
            let action = if row.action.eq_ignore_ascii_case("block") {
                FilterAction::Block
            } else {
                FilterAction::Allow
            };
            match FilterRule::try_new(row.id, &row.pattern, action, row.description) {
                Ok(rule) => new_rules.push(rule),
                Err(e)   => warn!("Règle ignorée: {}", e),
            }
        }

        let count = new_rules.len();
        *self.rules_cache.write().await = new_rules;
        info!("Cache des règles rafraîchi — {} règles actives", count);
        Ok(())
    }

    pub async fn refresh_client_cache(&self) -> Result<()> {
        // 1. Utilisateurs clients (IP → user_id)
        let users = sqlx::query_as::<_, ClientUserRow>(
            "SELECT id, ip_address FROM client_users"
        )
        .fetch_all(&self.db_pool)
        .await?;

        // 2. Appartenance aux groupes (many-to-many)
        let user_groups = sqlx::query_as::<_, ClientUserGroupRow>(
            "SELECT user_id, group_id FROM client_user_groups"
        )
        .fetch_all(&self.db_pool)
        .await?;

        // 3. Règles actives par groupe
        let group_rule_rows = sqlx::query_as::<_, GroupRuleRow>(
            "SELECT group_id, rule_id FROM group_rules"
        )
        .fetch_all(&self.db_pool)
        .await?;

        // 4. Groupe par défaut
        let default_group = sqlx::query_as::<_, DefaultGroupRow>(
            "SELECT id FROM client_groups WHERE is_default = TRUE LIMIT 1"
        )
        .fetch_optional(&self.db_pool)
        .await?;

        let mut cache = ClientCache::default();
        cache.default_group_id = default_group.map(|r| r.id);

        for u in users {
            cache.ip_to_user_id.insert(u.ip_address, u.id);
        }

        for ug in user_groups {
            cache.user_groups.entry(ug.user_id).or_default().push(ug.group_id);
        }

        let default_id = cache.default_group_id;
        for gr in group_rule_rows {
            if Some(gr.group_id) == default_id {
                cache.default_group_rules.insert(gr.rule_id);
            } else {
                cache.group_rules
                    .entry(gr.group_id)
                    .or_default()
                    .insert(gr.rule_id);
            }
        }

        // 5. Hôtes bypass (non filtrés)
        let bypass_rows = sqlx::query_as::<_, TlsBypassRow>(
            "SELECT host FROM tls_bypass"
        )
        .fetch_all(&self.db_pool)
        .await?;

        for r in bypass_rows {
            cache.tls_bypass.insert(r.host);
        }

        let ip_count     = cache.ip_to_user_id.len();
        let bypass_count = cache.tls_bypass.len();
        *self.client_cache.write().await = cache;
        info!("Cache clients rafraîchi — {} IP enregistrées, {} hôtes bypass", ip_count, bypass_count);
        Ok(())
    }

    // ── Killswitch ───────────────────────────────────────────────────────────

    /// Recharge l'état du killswitch depuis PostgreSQL.
    pub async fn refresh_killswitch(&self) -> Result<()> {
        let row: Option<(String,)> = sqlx::query_as(
            "SELECT value FROM app_settings WHERE key = 'killswitch'"
        )
        .fetch_optional(&self.db_pool)
        .await?;

        let active = row.map(|(v,)| v == "true").unwrap_or(false);
        let was    = self.killswitch.swap(active, Ordering::Relaxed);

        if active && !was {
            warn!("🔴 KILLSWITCH ACTIVÉ — tout le trafic est autorisé sans filtrage !");
        } else if !active && was {
            info!("🟢 Killswitch désactivé — filtrage rétabli.");
        }
        Ok(())
    }

    // ── Filtrage ─────────────────────────────────────────────────────────────

    /// Détermine si une URL doit être bloquée pour un client donné.
    ///
    /// Chaîne de priorité :
    ///   1. Groupes explicites : tous les groupes de l'utilisateur sont examinés.
    ///      Si AUCUN groupe autorise ET qu'au moins un bloque → bloqué.
    ///      Un groupe avec une règle Allow prend le dessus sur tout blocage (privilège).
    ///   2. Groupe par défaut (utilisateur sans groupe / IP inconnue)
    ///   3. Règle globale directe (si aucun groupe par défaut configuré)
    pub async fn is_blocked(&self, client_ip: &str, url: &str) -> bool {
        // Killswitch : court-circuit immédiat, lock-free
        if self.killswitch.load(Ordering::Relaxed) {
            debug!("[KILLSWITCH] actif — {} autorisé", url);
            return false;
        }

        let rules   = self.rules_cache.read().await;
        let clients = self.client_cache.read().await;

        let user_id = clients.ip_to_user_id.get(client_ip);

        // ── Log de contexte : qui fait la requête ────────────────────────────
        match user_id {
            None => debug!(
                "[FILTRAGE] IP={} → non enregistrée → groupe par défaut | url={}",
                client_ip, url
            ),
            Some(&uid) => {
                let groups = clients.user_groups.get(&uid);
                let glist  = groups
                    .map(|g| g.iter().map(|id| id.to_string()).collect::<Vec<_>>().join(", "))
                    .unwrap_or_else(|| "aucun".to_owned());
                debug!(
                    "[FILTRAGE] IP={} → user_id={} → groupes=[{}] | nb_règles={} | url={}",
                    client_ip, uid, glist, rules.len(), url
                );
            }
        }

        // ── Niveau 1 : utilisateur connu avec groupes explicites ─────────────
        if let Some(&uid) = user_id {
            if let Some(groups) = clients.user_groups.get(&uid) {
                if !groups.is_empty() {
                    // Les règles sont triées par priorité croissante (plus petit = plus prioritaire).
                    // La première règle qui matche ET qui est active dans au moins un groupe gagne.
                    for rule in rules.iter() {
                        if !rule.matches(url) { continue; }

                        let active_group = groups.iter().find(|&&gid| {
                            clients.group_rules.get(&gid)
                                .map(|rs| rs.contains(&rule.id))
                                .unwrap_or(false)
                        });

                        if let Some(&gid) = active_group {
                            let blocked = rule.action == FilterAction::Block;
                            debug!(
                                "  → groupe {} → règle id={} pat='{}' ({:?}) → {}",
                                gid, rule.id, rule.pattern, rule.action,
                                if blocked { "BLOQUÉ" } else { "AUTORISÉ" }
                            );
                            return blocked;
                        }

                        debug!(
                            "  [règle id={} pat='{}' {:?}] correspond mais absente de tous les groupes → ignorée",
                            rule.id, rule.pattern, rule.action
                        );
                    }

                    debug!("  → AUTORISÉ (aucune règle active ne correspond)");
                    return false;
                } else {
                    debug!("  → user {} n'a aucun groupe → groupe par défaut", uid);
                }
            } else {
                debug!("  → user {} absent de user_groups → groupe par défaut", uid);
            }
        }

        // ── Niveau 2 : groupe par défaut (utilisateur sans groupe / IP inconnue) ──
        for rule in rules.iter() {
            if !rule.matches(url) { continue; }
            if clients.default_group_id.is_some() {
                if clients.default_group_rules.contains(&rule.id) {
                    debug!(
                        "  → groupe par défaut : règle {} ({:?}) → {}",
                        rule.id, rule.action,
                        if rule.action == FilterAction::Block { "BLOQUÉ" } else { "AUTORISÉ" }
                    );
                    return rule.action == FilterAction::Block;
                }
                continue;
            }

            // ── Niveau 3 : règle globale (aucun groupe par défaut configuré) ───
            debug!(
                "  → règle globale {} ({:?}) → {}",
                rule.id, rule.action,
                if rule.action == FilterAction::Block { "BLOQUÉ" } else { "AUTORISÉ" }
            );
            return rule.action == FilterAction::Block;
        }

        debug!("  → aucune règle ne correspond → AUTORISÉ par défaut");
        false
    }

    // ── Bypass ───────────────────────────────────────────────────────────────

    /// Retourne `true` si l'hôte est exempté du filtrage (configuré en DB).
    pub async fn is_bypass_host(&self, host: &str) -> bool {
        let clients = self.client_cache.read().await;
        clients.tls_bypass.iter().any(|e| host_matches_entry(host, e))
    }

    // ── Logging async ────────────────────────────────────────────────────────

    /// Enregistre un accès en base de façon asynchrone (fire-and-forget).
    pub fn log_access_background(
        &self,
        client_ip:  String,
        url:        String,
        method:     String,
        blocked:    bool,
        user_agent: Option<String>,
    ) {
        let pool = self.db_pool.clone();
        tokio::spawn(async move {
            let result = sqlx::query(
                r#"
                INSERT INTO access_logs (client_ip, url, method, blocked, user_agent, accessed_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                "#,
            )
            .bind(&client_ip)
            .bind(&url)
            .bind(&method)
            .bind(blocked)
            .bind(user_agent.as_deref())
            .execute(&pool)
            .await;

            if let Err(e) = result {
                error!("Erreur lors de l'enregistrement de l'accès: {}", e);
            }
        });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Handler HTTP/HTTPS
// ─────────────────────────────────────────────────────────────────────────────

/// Handler injecté dans hudsucker, cloné pour chaque connexion cliente.
#[derive(Clone)]
pub struct ProxyHandler {
    state: AppState,
}

impl ProxyHandler {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }
}

fn host_matches_entry(host: &str, entry: &str) -> bool {
    host == entry || host.ends_with(&format!(".{}", entry))
}

#[async_trait]
impl HttpHandler for ProxyHandler {
    /// Appelé avant chaque requête sortante.
    async fn handle_request(
        &mut self,
        ctx: &HttpContext,
        req: Request<Body>,
    ) -> RequestOrResponse {
        let method    = req.method().to_string();
        let client_ip = ctx.client_addr.ip().to_string();
        let user_agent = req
            .headers()
            .get(header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned);

        // Hôte depuis l'URI (HTTP absolu) ou depuis le header Host (HTTPS intercepté)
        let host = req.uri().host()
            .map(str::to_owned)
            .or_else(|| {
                req.headers()
                    .get(header::HOST)
                    .and_then(|v| v.to_str().ok())
                    .map(|h| h.split(':').next().unwrap_or(h).to_owned())
            })
            .unwrap_or_else(|| "unknown".to_owned());

        // ── 1. Interface d'administration Grand-Duc ───────────────────────
        if host == ADMIN_HOST {
            info!("ADMIN    [{method}] {}", req.uri());
            return RequestOrResponse::Response(serve_asset(req.uri().path()));
        }

        // ── 2. CONNECT : laisser hudsucker faire le MitM TLS ─────────────
        // On ne bloque JAMAIS au stade CONNECT : les navigateurs n'affichent
        // pas le body HTML d'une réponse 403 à un CONNECT, ils affichent leur
        // propre page d'erreur. Le blocage réel se fait sur la requête HTTP
        // décryptée (étape 4 ci-dessous).
        // Le CONNECT est loggé en DB pour permettre de voir tout le trafic
        // (notamment les apps qui échouent au niveau TLS sans générer de HTTP).
        if method == "CONNECT" {
            let bypass = self.state.is_bypass_host(&host).await;
            if bypass {
                info!("BYPASS   [CONNECT] {}", req.uri());
            } else {
                info!("TUNNEL   [CONNECT] {}", req.uri());
            }
            self.state.log_access_background(
                client_ip,
                req.uri().to_string(),  // format "host:port"
                "CONNECT".to_owned(),
                false,
                user_agent,
            );
            return RequestOrResponse::Request(req);
        }

        // ── 3. Reconstruire l'URL effective ──────────────────────────────
        // Pour les requêtes HTTPS interceptées par hudsucker, l'URI est
        // relative ("/" ou "/path?q=…"). On reconstruit l'URL complète
        // depuis le header Host.
        let effective_url = if req.uri().scheme().is_none() && host != "unknown" {
            let pq = req.uri().path_and_query().map(|pq| pq.as_str()).unwrap_or("/");
            format!("https://{}{}", host, pq)
        } else {
            req.uri().to_string()
        };

        // ── 4. Bypass hôte (trafic non filtré) ───────────────────────────
        if self.state.is_bypass_host(&host).await {
            info!("BYPASS   [{method}] {effective_url}");
            self.state.log_access_background(
                client_ip, effective_url, method, false, user_agent,
            );
            return RequestOrResponse::Request(req);
        }

        // ── 5. Filtrage ───────────────────────────────────────────────────
        if self.state.is_blocked(&client_ip, &effective_url).await {
            warn!("BLOQUÉ   [{method}] {effective_url}");
            self.state.log_access_background(
                client_ip, effective_url.clone(), method, true, user_agent,
            );
            return RequestOrResponse::Response(build_blocked_response(&effective_url));
        }

        // ── 6. Trafic autorisé ────────────────────────────────────────────
        info!("AUTORISÉ [{method}] {effective_url}");
        self.state.log_access_background(
            client_ip, effective_url, method, false, user_agent,
        );
        RequestOrResponse::Request(req)
    }

    async fn handle_response(
        &mut self,
        _ctx: &HttpContext,
        res: Response<Body>,
    ) -> Response<Body> {
        res
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Fonctions utilitaires — Réponses HTTP
// ─────────────────────────────────────────────────────────────────────────────

fn resolve_path(relative: &str) -> PathBuf {
    // GRAND_DUC_ROOT permet de pointer vers le projet en dev ou en prod
    std::env::var("GRAND_DUC_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::current_exe()
                .unwrap()
                .parent().unwrap()
                .to_path_buf()
        })
        .join(relative)
}

/// Sert un fichier depuis les builds frontend embarqués.
/// - /blocked/...  → BLOCKED_DIST
/// - /*            → DIST  (interface admin)
fn serve_asset(path: &str) -> Response<Body> {
    let (base_dir, clean) = (resolve_path("templates/blocked"), path.trim_start_matches('/').to_string());

    let is_asset = Path::new(&clean).extension().is_some();

    let file_path = {
        let requested = Path::new(&base_dir).join(&clean);
        if requested.is_file() {
            Some(requested)
        } else if !is_asset {
            let index = Path::new(&base_dir).join("index.html");
            if index.is_file() { Some(index) } else { None }
        } else {
            None
        }
    };

    match file_path {
        Some(path) => {
            match std::fs::read(&path) {
                Ok(bytes) => {
                    let mime  = from_path(&path).first_or_octet_stream();
                    let cache = if clean.is_empty() || clean == "index.html" {
                        "no-cache"
                    } else {
                        "public, max-age=31536000, immutable"
                    };
                    Response::builder()
                        .status(StatusCode::OK)
                        .header(header::CONTENT_TYPE, mime.as_ref())
                        .header(header::CACHE_CONTROL, cache)
                        .body(Body::from(bytes))
                        .expect("Construction de la réponse asset impossible")
                }
                Err(e) => {
                    error!("Lecture fichier échouée {:?}: {}", path, e);
                    Response::builder()
                        .status(StatusCode::INTERNAL_SERVER_ERROR)
                        .body(Body::from("Erreur lecture fichier"))
                        .unwrap()
                }
            }
        }
        None => Response::builder()
            .status(StatusCode::NOT_FOUND)
            .header(header::CONTENT_TYPE, "text/plain; charset=utf-8")
            .body(Body::from("404 — Ressource introuvable"))
            .unwrap(),
    }
}

/// Retourne l'index.html du build "blocked" en y injectant l'URL bloquée.
/// Le frontend la récupère via window.__BLOCKED_URL__
fn build_blocked_response(url: &str) -> Response<Body> {
    let index_path = resolve_path("templates/blocked/index.html");
    let index = std::fs::read_to_string(&index_path)
        .unwrap_or_else(|e| {
            error!("Impossible de lire {:?}: {}", index_path, e);
            "<html><body>Accès bloqué</body></html>".to_owned()
        });

    let injection = format!(
        r#"<base href="https://grand-duc.proxy/blocked/"><script>window.__BLOCKED_URL__ = "{}";</script>"#,
        html_escape(url)
    );

    let html = if let Some(pos) = index.find("<head>") {
        let insert_at = pos + "<head>".len();
        format!("{}{}{}", &index[..insert_at], injection, &index[insert_at..])
    } else if let Some(pos) = index.find("<head ") {
        let insert_at = index[pos..].find('>').map(|i| pos + i + 1).unwrap_or(pos);
        format!("{}{}{}", &index[..insert_at], injection, &index[insert_at..])
    } else {
        format!("{}{}", injection, index)
    };

    Response::builder()
        .status(StatusCode::FORBIDDEN)
        .header(header::CONTENT_TYPE, "text/html; charset=utf-8")
        .header(header::CACHE_CONTROL, "no-store")
        .body(Body::from(html))
        .expect("Construction de la réponse de blocage impossible")
}

/// Échappe les caractères HTML spéciaux pour éviter les injections XSS
/// dans la page de blocage.
fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}

// ─────────────────────────────────────────────────────────────────────────────
// Autorité de Certification (CA)
// ─────────────────────────────────────────────────────────────────────────────

/// Charge ou génère une CA persistante sur disque.
///
/// Fichiers créés au premier lancement dans le répertoire courant :
///   grand-duc-ca.key  → clé privée PKCS#8 DER  (garder SECRET)
///   grand-duc-ca.crt  → certificat X.509 PEM    (distribuer aux postes)
fn build_ca() -> Result<RcgenAuthority> {
    use hudsucker::rustls::{Certificate as RustlsCert, PrivateKey as RustlsKey};

    let key_path  = Path::new("grand-duc-ca.key");
    let cert_path = Path::new("grand-duc-ca.crt");

    let (key_der, cert_der) = if key_path.exists() && cert_path.exists() {
        info!("Chargement de la CA depuis le disque…");
        let key_der  = std::fs::read(key_path)?;
        let pem_str  = std::fs::read_to_string(cert_path)?;
        let cert_der = pem_to_der(&pem_str)?;
        (key_der, cert_der)
    } else {
        info!("Génération d'une nouvelle CA (premier lancement)…");
        let key_pair = KeyPair::generate()?;

        let mut params = CertificateParams::default();
        params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
        params.distinguished_name.push(rcgen::DnType::CommonName,       "Grand-Duc Proxy CA");
        params.distinguished_name.push(rcgen::DnType::OrganizationName, "SOCODEP");
        params.distinguished_name.push(rcgen::DnType::CountryName,      "FR");
        params.not_before = rcgen::date_time_ymd(2025, 1, 1);
        params.not_after  = rcgen::date_time_ymd(2035, 1, 1);

        let ca_cert  = params.self_signed(&key_pair)?;
        let key_der  = key_pair.serialize_der();
        let cert_der = ca_cert.der().to_vec();

        std::fs::write(key_path, &key_der)?;
        std::fs::write(cert_path, der_to_pem(&cert_der, "CERTIFICATE"))?;

        info!("CA sauvegardée → grand-duc-ca.crt  (à distribuer aux postes)");
        (key_der, cert_der)
    };

    RcgenAuthority::new(RustlsKey(key_der), RustlsCert(cert_der), 1_000)
        .map_err(|e| anyhow!("Erreur création CA: {}", e))
}

// ── Helpers PEM ───────────────────────────────────────────────────────────────

fn der_to_pem(der: &[u8], label: &str) -> String {
    use std::fmt::Write;
    let b64 = base64_encode(der);
    let mut pem = format!("-----BEGIN {}-----\n", label);
    for chunk in b64.as_bytes().chunks(64) {
        pem.push_str(std::str::from_utf8(chunk).unwrap());
        pem.push('\n');
    }
    write!(pem, "-----END {}-----\n", label).unwrap();
    pem
}

fn pem_to_der(pem: &str) -> Result<Vec<u8>> {
    let b64: String = pem.lines()
        .filter(|l| !l.starts_with("-----"))
        .collect();
    base64_decode(&b64)
}

fn base64_encode(data: &[u8]) -> String {
    use std::io::Write;
    let mut enc = Vec::new();
    {
        let mut encoder = base64::write::EncoderWriter::new(
            &mut enc,
            &base64::engine::general_purpose::STANDARD,
        );
        encoder.write_all(data).unwrap();
    }
    String::from_utf8(enc).unwrap()
}

fn base64_decode(s: &str) -> Result<Vec<u8>> {
    use base64::Engine;
    base64::engine::general_purpose::STANDARD
        .decode(s)
        .map_err(|e| anyhow!("Erreur décodage base64 PEM: {}", e))
}

// ─────────────────────────────────────────────────────────────────────────────
// Console Windows
// ─────────────────────────────────────────────────────────────────────────────

/// Active le traitement des séquences ANSI dans cmd.exe sur Windows.
#[cfg(windows)]
fn enable_ansi_console() {
    use windows_sys::Win32::System::Console::{
        GetConsoleMode, GetStdHandle, SetConsoleMode,
        ENABLE_VIRTUAL_TERMINAL_PROCESSING, STD_OUTPUT_HANDLE,
    };
    unsafe {
        let handle = GetStdHandle(STD_OUTPUT_HANDLE);
        let mut mode = 0u32;
        if GetConsoleMode(handle, &mut mode) != 0 {
            SetConsoleMode(handle, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
        }
    }
}

#[cfg(not(windows))]
fn enable_ansi_console() {}

// ─────────────────────────────────────────────────────────────────────────────
// Point d'entrée
// ─────────────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> Result<()> {
    enable_ansi_console();

    // ── Logging ───────────────────────────────────────────────────────────────
    let env_filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "grand_duc=debug,warn".into());

    // Fichier de log (sans couleurs ANSI) pour la page d'administration
    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("grand-duc.log")
        .expect("Impossible d'ouvrir grand-duc.log");

    let file_layer = tracing_subscriber::fmt::layer()
        .with_ansi(false)
        .with_writer(std::sync::Mutex::new(log_file));

    let stdout_layer = tracing_subscriber::fmt::layer()
        .with_ansi(true);

    tracing_subscriber::registry()
        .with(env_filter)
        .with(stdout_layer)
        .with(file_layer)
        .init();

    // ── Configuration ─────────────────────────────────────────────────────────
    let database_url = std::env::var("DATABASE_URL_PROXY").unwrap_or_else(|_| {
        "postgresql://proxy_user:password@localhost/proxy_db".to_owned()
    });
    let listen_addr: SocketAddr = std::env::var("PROXY_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_owned())
        .parse()
        .map_err(|e| anyhow!("PROXY_ADDR invalide: {}", e))?;

    // ── Connexion DB + chargement initial du cache ─────────────────────────
    info!("Connexion à PostgreSQL…");
    let state = AppState::new(&database_url).await?;

    // ── Tâche de rafraîchissement périodique du cache (toutes les 5 min) ──
    {
        let state_bg = state.clone();
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(300));
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
            loop {
                interval.tick().await;
                if let Err(e) = state_bg.refresh_rules_cache().await {
                    error!("Rafraîchissement du cache échoué: {}", e);
                }
                if let Err(e) = state_bg.refresh_client_cache().await {
                    error!("Rafraîchissement clients échoué: {}", e);
                } 
            }
        });
    }

    // ── Tâche de rafraîchissement rapide du killswitch (toutes les 10s) ───
    {
        let state_bg = state.clone();
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(10));
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
            loop {
                interval.tick().await;
                if let Err(e) = state_bg.refresh_killswitch().await {
                    error!("Rafraîchissement killswitch échoué: {}", e);
                }
            }
        });
    }

    // ── Construction de la CA ─────────────────────────────────────────────
    let ca = build_ca()?;
    info!("CA prête (rustls)");

    // ── Arrêt gracieux via CTRL+C ─────────────────────────────────────────
    let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();
    tokio::spawn(async move {
        if tokio::signal::ctrl_c().await.is_ok() {
            info!("Signal CTRL+C reçu — arrêt gracieux en cours…");
        }
        let _ = shutdown_tx.send(());
    });

    // ── Démarrage du proxy ────────────────────────────────────────────────
    info!("Grand-Duc en écoute sur {}  (admin → http://{}/ )", listen_addr, ADMIN_HOST);

    ProxyBuilder::new()
        .with_addr(listen_addr)
        .with_rustls_client()
        .with_ca(ca)
        .with_http_handler(ProxyHandler::new(state))
        .build()
        .start(async move {
            let _: Result<(), _> = shutdown_rx.await;
        })
        .await
        .map_err(|e| anyhow!("Erreur d'exécution du proxy: {}", e))?;

    info!("Grand-Duc arrêté proprement.");
    Ok(())
}