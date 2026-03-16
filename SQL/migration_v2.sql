-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v2 : table users
-- psql -U hibou -d grand_duc -f migration_v2.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Table utilisateurs de l'interface d'administration ───────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL    PRIMARY KEY,
    username        TEXT         NOT NULL UNIQUE,
    email           TEXT,
    hashed_password TEXT         NOT NULL,
    role            TEXT         NOT NULL DEFAULT 'viewer'
                                 CHECK (role IN ('admin', 'viewer')),
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

-- ── Ajout colonne client_ip sur access_logs (si absente) ─────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'access_logs' AND column_name = 'client_ip'
    ) THEN
        ALTER TABLE access_logs ADD COLUMN client_ip TEXT;
    END IF;
END $$;

-- ── Droits ────────────────────────────────────────────────────────────────────
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO hibou;
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO hibou;

-- ── Compte admin initial (mot de passe : changeme — à modifier immédiatement) ─
-- Hash bcrypt de "changeme" généré hors-ligne
INSERT INTO users (username, email, hashed_password, role)
VALUES ('admin', '', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.iK8i', 'admin') ON CONFLICT (username) DO NOTHING;
