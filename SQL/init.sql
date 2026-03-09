-- ─────────────────────────────────────────────────────────────────────────────
-- Corp Proxy — Schéma PostgreSQL
-- Exécuter une seule fois sur la base cible :
--   psql -U proxy_user -d proxy_db -f sql/init.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Règles de filtrage ────────────────────────────────────────────────────────
-- Chaque ligne correspond à une règle compilée par le proxy au démarrage
-- (ou lors du rafraîchissement périodique du cache).
--
-- Colonnes importantes :
--   pattern  : expression régulière Rust (crate `regex`) matchée sur l'URL complète
--   action   : 'block' ou 'allow'
--   priority : les règles sont évaluées dans l'ordre croissant de priority ;
--              la PREMIÈRE correspondance l'emporte
--   enabled  : permet de désactiver une règle sans la supprimer

CREATE TABLE IF NOT EXISTS filter_rules (
    id          BIGSERIAL    PRIMARY KEY,
    pattern     TEXT         NOT NULL,
    action      TEXT         NOT NULL CHECK (action IN ('block', 'allow')),
    description TEXT,
    priority    INTEGER      NOT NULL DEFAULT 100,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index utilisé par la requête de chargement du cache
CREATE INDEX IF NOT EXISTS idx_filter_rules_active
    ON filter_rules (priority ASC)
    WHERE enabled = TRUE;

-- ── Journal des accès ─────────────────────────────────────────────────────────
-- Chaque requête interceptée par le proxy génère une ligne.
-- Le proxy insère en mode fire-and-forget (pas de latence côté client).

CREATE TABLE IF NOT EXISTS access_logs (
    id          BIGSERIAL    PRIMARY KEY,
    host        TEXT         NOT NULL,
    url         TEXT         NOT NULL,
    method      TEXT         NOT NULL DEFAULT 'CONNECT',
    blocked     BOOLEAN      NOT NULL,
    user_agent  TEXT,
    accessed_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index pour les requêtes de reporting les plus courantes
CREATE INDEX IF NOT EXISTS idx_access_logs_date
    ON access_logs (accessed_at DESC);

CREATE INDEX IF NOT EXISTS idx_access_logs_host
    ON access_logs (host);

CREATE INDEX IF NOT EXISTS idx_access_logs_blocked
    ON access_logs (blocked)
    WHERE blocked = TRUE;

-- ── Trigger : mise à jour automatique de updated_at ─────────────────────────
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON filter_rules
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

-- ── Données initiales : exemples de règles ────────────────────────────────────
-- Ajustez les patterns selon votre politique de sécurité.
-- Les patterns sont des expressions régulières Rust (crate `regex`).

INSERT INTO filter_rules (pattern, action, description, priority) VALUES
    -- Très haute priorité : menaces connues
    ('(?i)(malware|ransomware|phishing|exploit-kit)',
     'block', 'Contenu malveillant connu', 1),

    -- Téléchargements exécutables
    ('(?i)\.(exe|msi|bat|cmd|ps1|vbs|js|jar)(\?.*)?$',
     'block', 'Téléchargements exécutables', 5),

    -- Réseaux sociaux
    ('^https?://(www\.)?(facebook|instagram|tiktok|snapchat|twitter|x)\.com',
     'block', 'Réseaux sociaux', 10),

    -- Streaming vidéo grand public
    ('^https?://(www\.)?(youtube|netflix|twitch|dailymotion)\.com',
     'block', 'Streaming vidéo non professionnel', 20),

    -- Exemple de liste blanche (allow en priorité basse surclasse tout)
    ('^https?://(www\.)?socodep\.fr',
     'allow', 'Site SOCODEP — toujours autorisé', 200)

ON CONFLICT DO NOTHING;