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
//!   DATABASE_URL  postgresql://user:pass@host/db   (requis)
//!   PROXY_ADDR    0.0.0.0:8080                     (optionnel, défaut : 0.0.0.0:8080)
//!
//! Interface d'administration :
//!   Configurer le proxy navigateur sur 127.0.0.1:8080, puis visiter http://grand-duc.proxy/

use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use std::path::Path;

use anyhow::{anyhow, Result};
use hudsucker::{
    async_trait::async_trait,
    certificate_authority::RcgenAuthority,
    hyper::{header, Body, Request, Response, StatusCode},
    HttpContext, HttpHandler, ProxyBuilder, RequestOrResponse,
};
use include_dir::{include_dir, Dir};
use mime_guess::from_path;
use rcgen::{BasicConstraints, CertificateParams, IsCa, KeyPair};
use regex::Regex;
use sqlx::PgPool;
use tokio::sync::RwLock;
use tracing::{error, info, warn};

// ── Assets statiques ─────────────────────────────────────────────────────────

/// Build frontend Vue/React de l'interface d'administration
static DIST: Dir = include_dir!("$CARGO_MANIFEST_DIR/templates/blocked");

/// Build frontend Vue/React de la page de blocage
static BLOCKED_DIST: Dir = include_dir!("$CARGO_MANIFEST_DIR/templates/blocked");


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

// ── Ligne brute lue depuis PostgreSQL ────────────────────────────────────────

#[derive(sqlx::FromRow)]
struct FilterRuleRow {
    id:          i64,
    pattern:     String,
    action:      String,
    description: Option<String>,
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
    pub rules_cache: Arc<RwLock<Vec<FilterRule>>>,
}

impl AppState {
    /// Initialise le state : connexion PostgreSQL + premier chargement du cache.
    pub async fn new(database_url: &str) -> Result<Self> {
        let db_pool = PgPool::connect(database_url).await?;
        let state = Self {
            db_pool,
            rules_cache: Arc::new(RwLock::new(Vec::new())),
        };
        state.refresh_rules_cache().await?;
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
             ORDER BY priority ASC
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

    // ── Filtrage ─────────────────────────────────────────────────────────────

    /// Détermine si une URL doit être bloquée.
    pub async fn is_blocked(&self, url: &str) -> bool {
        let rules = self.rules_cache.read().await;
        for rule in rules.iter() {
            if rule.matches(url) {
                return rule.action == FilterAction::Block;
            }
        }
        false
    }

    // ── Logging async ────────────────────────────────────────────────────────

    /// Enregistre un accès en base de façon asynchrone (fire-and-forget).
    pub fn log_access_background(
        &self,
        host:       String,
        url:        String,
        method:     String,
        blocked:    bool,
        user_agent: Option<String>,
    ) {
        let pool = self.db_pool.clone();
        tokio::spawn(async move {
            let result = sqlx::query(
                r#"
                INSERT INTO access_logs (host, url, method, blocked, user_agent, accessed_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                "#,
            )
            .bind(&host)
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

#[async_trait]
impl HttpHandler for ProxyHandler {
    /// Appelé avant chaque requête sortante.
    async fn handle_request(
        &mut self,
        _ctx: &HttpContext,
        req: Request<Body>,
    ) -> RequestOrResponse {
        let method     = req.method().to_string();
        let uri        = req.uri().to_string();
        let host       = req.uri().host().unwrap_or("unknown").to_owned();
        let user_agent = req
            .headers()
            .get(header::USER_AGENT)
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned);

        // ── 1. Interface d'administration Grand-Duc ───────────────────────
        if host == ADMIN_HOST {
            info!("ADMIN    [{method}] {uri}");
            return RequestOrResponse::Response(serve_asset(req.uri().path()));
        }

        // ── 2. Filtrage ───────────────────────────────────────────────────
        if self.state.is_blocked(&uri).await {
            warn!("BLOQUÉ   [{method}] {uri}");
            self.state.log_access_background(
                host, uri.clone(), method, true, user_agent,
            );
            return RequestOrResponse::Response(build_blocked_response(&uri));
        }

        // ── 3. Trafic autorisé ────────────────────────────────────────────
        info!("AUTORISÉ [{method}] {uri}");
        self.state.log_access_background(
            host, uri, method, false, user_agent,
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

/// Sert un fichier depuis les builds frontend embarqués.
/// - /blocked/...  → BLOCKED_DIST
/// - /*            → DIST  (interface admin)
fn serve_asset(path: &str) -> Response<Body> {
    let (dist, clean) = if let Some(rest) = path.strip_prefix("/blocked/") {
        (&BLOCKED_DIST, rest)
    } else {
        (&DIST, path.trim_start_matches('/'))
    };

    // Fallback index.html uniquement pour les routes SPA (pas d'extension)
    // Les assets (.js, .css, .webp…) retournent 404 s'ils sont absents
    let is_asset = Path::new(clean).extension().is_some();
    let file = dist.get_file(clean)
                   .or_else(|| if !is_asset { dist.get_file("index.html") } else { None });

    match file {
        Some(f) => {
            let mime  = from_path(f.path()).first_or_octet_stream();
            let cache = if clean.is_empty() || clean == "index.html" {
                "no-cache"
            } else {
                "public, max-age=31536000, immutable"
            };
            Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, mime.as_ref())
                .header(header::CACHE_CONTROL, cache)
                .body(Body::from(f.contents()))
                .expect("Construction de la réponse asset impossible")
        }
        None => Response::builder()
            .status(StatusCode::NOT_FOUND)
            .header(header::CONTENT_TYPE, "text/plain; charset=utf-8")
            .body(Body::from("404 — Ressource introuvable"))
            .expect("Construction de la réponse 404 impossible"),
    }
}

/// Retourne l'index.html du build "blocked" en y injectant l'URL bloquée.
/// Le frontend la récupère via window.__BLOCKED_URL__
fn build_blocked_response(url: &str) -> Response<Body> {
    let index = BLOCKED_DIST
        .get_file("index.html")
        .and_then(|f| std::str::from_utf8(f.contents()).ok())
        .unwrap_or("<html><body>Accès bloqué</body></html>");

    let injection = format!(
        r#"<base href="http://grand-duc.proxy/blocked/">
<script>window.__BLOCKED_URL__ = "{}";</script>"#,
        html_escape(url)
    );

    // Injecte avant </head>, ou en tête de document si absent
    let html = if let Some(pos) = index.find("</head>") {
        format!("{}{}{}", &index[..pos], injection, &index[pos..])
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
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "grand_duc=info,warn".into()),
        )
        .with_ansi(true)
        .init();

    // ── Configuration ─────────────────────────────────────────────────────────
    let database_url = std::env::var("DATABASE_URL").unwrap_or_else(|_| {
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