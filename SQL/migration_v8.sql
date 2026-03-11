-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v8 : table killswitch_history
-- psql -U hibou -d grand_duc -f migration_v8.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS killswitch_history (
    id         BIGSERIAL PRIMARY KEY,
    action     TEXT        NOT NULL,          -- 'activated' | 'deactivated'
    username   TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT ON killswitch_history TO hibou;
GRANT USAGE, SELECT ON SEQUENCE killswitch_history_id_seq TO hibou;
