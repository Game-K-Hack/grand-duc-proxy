-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v7 : table app_settings (killswitch)
-- psql -U hibou -d grand_duc -f migration_v7.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

GRANT SELECT, INSERT, UPDATE, DELETE ON app_settings TO hibou;

INSERT INTO app_settings (key, value) VALUES ('killswitch', 'false')
ON CONFLICT (key) DO NOTHING;
