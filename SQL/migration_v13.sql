-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v13 : colonnes manquantes, index, user_themes,
--                              mot de passe temporaire
-- Regroupe les modifications faites en Python (_ensure_columns, _ensure_indexes)
-- et les ajouts manuels non présents dans les migrations précédentes.
-- psql -U hibou -d grand_duc -f migration_v13.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Table user_themes (préférences de thème par utilisateur) ────────────────
CREATE TABLE IF NOT EXISTS user_themes (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    theme   TEXT   NOT NULL DEFAULT '{}'
);

GRANT SELECT, INSERT, UPDATE, DELETE ON user_themes TO hibou;

-- ── Colonnes manquantes ─────────────────────────────────────────────────────
ALTER TABLE client_users     ADD COLUMN IF NOT EXISTS logged_user          TEXT;
ALTER TABLE rmm_integrations ADD COLUMN IF NOT EXISTS auto_group_by       VARCHAR(20) DEFAULT 'none';
ALTER TABLE users            ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

-- ── Index performance sur access_logs ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS ix_access_logs_accessed_at         ON access_logs (accessed_at);
CREATE INDEX IF NOT EXISTS ix_access_logs_blocked_accessed_at ON access_logs (blocked, accessed_at);
CREATE INDEX IF NOT EXISTS ix_access_logs_client_ip           ON access_logs (client_ip);
CREATE INDEX IF NOT EXISTS ix_access_logs_host                ON access_logs (host);

-- ── Mise à jour des permissions des rôles built-in ────────────────────────
-- Ajoute les nouvelles permissions (templates, appearance) manquantes dans v12
UPDATE roles SET permissions = '{"dashboard.read":true,"rules.read":true,"rules.write":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_groups.write":true,"client_users.read":true,"client_users.write":true,"test_access.use":true,"users.read":true,"users.write":true,"tls_bypass.read":true,"tls_bypass.write":true,"killswitch.read":true,"killswitch.write":true,"certificates.read":true,"certificates.write":true,"settings.smtp.read":true,"settings.smtp.write":true,"settings.templates.read":true,"settings.templates.write":true,"settings.appearance.read":true,"settings.appearance.write":true,"settings.rmm.read":true,"settings.rmm.write":true,"roles.read":true,"roles.write":true,"proxy.restart":true}'
WHERE name = 'Administrateur' AND is_builtin = TRUE;

UPDATE roles SET permissions = '{"dashboard.read":true,"rules.read":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_users.read":true,"users.read":true,"tls_bypass.read":true,"killswitch.read":true,"certificates.read":true,"settings.smtp.read":true,"settings.templates.read":true,"settings.appearance.read":true,"settings.rmm.read":true,"roles.read":true}'
WHERE name = 'Lecteur' AND is_builtin = TRUE;

-- ── Forcer le changement de mot de passe pour le compte admin initial ─────
UPDATE users SET must_change_password = TRUE, hashed_password = '$2b$12$rBqfOWBZQkMt1a2W1QaAJO39kHFqCeSjGOZJTfadyrzsdJAqYx1WO' WHERE username = 'admin';

-- ── Corriger le groupe par défaut (v4 le recrée sans is_default) ──────────
UPDATE client_groups SET is_default = TRUE WHERE name = 'Défaut';