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