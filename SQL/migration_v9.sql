-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v9 : table certificate_history
-- psql -U hibou -d grand_duc -f migration_v9.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS certificate_history (
    id          BIGSERIAL    PRIMARY KEY,
    action      TEXT         NOT NULL,          -- 'generated' | 'imported'
    username    TEXT         NOT NULL,
    subject     TEXT,
    fingerprint TEXT,                            -- SHA-256 hex
    not_before  TIMESTAMPTZ,
    not_after   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT ON certificate_history TO hibou;
GRANT USAGE, SELECT ON SEQUENCE certificate_history_id_seq TO hibou;
