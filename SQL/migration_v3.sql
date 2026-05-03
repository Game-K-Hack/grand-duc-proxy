-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v3 : gestion clients par IP + groupes + overrides
-- psql -U hibou -d grand_duc -f migration_v3.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Groupes de clients ────────────────────────────────────────────────────────
-- Un groupe rassemble des utilisateurs et peut avoir ses propres overrides
-- de règles (bloquer ou autoriser spécifiquement certaines règles).
CREATE TABLE IF NOT EXISTS client_groups (
    id          BIGSERIAL   PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Utilisateurs clients (identifiés par adresse IP) ─────────────────────────
-- Un utilisateur peut appartenir à 0 ou 1 groupe.
-- Les overrides utilisateur ont la priorité maximale.
CREATE TABLE IF NOT EXISTS client_users (
    id          BIGSERIAL   PRIMARY KEY,
    ip_address  TEXT        NOT NULL UNIQUE,
    label       TEXT,                                    -- nom lisible, ex: "Poste Utilisateur"
    group_id    BIGINT      REFERENCES client_groups(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_users_ip    ON client_users (ip_address);
CREATE INDEX IF NOT EXISTS idx_client_users_group ON client_users (group_id);

-- ── Overrides de règles par groupe ────────────────────────────────────────────
-- Permet de modifier l'action d'une règle globale pour un groupe entier.
-- Exemples :
--   - Règle globale "block YouTube" → override group "Directeurs" → allow
--   - Règle globale "allow *" → override group "Stagiaires" → block
CREATE TABLE IF NOT EXISTS group_rule_overrides (
    id          BIGSERIAL   PRIMARY KEY,
    group_id    BIGINT      NOT NULL REFERENCES client_groups(id) ON DELETE CASCADE,
    rule_id     BIGINT      NOT NULL REFERENCES filter_rules(id)  ON DELETE CASCADE,
    action      TEXT        NOT NULL CHECK (action IN ('block', 'allow')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (group_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_gro_group ON group_rule_overrides (group_id);
CREATE INDEX IF NOT EXISTS idx_gro_rule  ON group_rule_overrides (rule_id);

-- ── Overrides de règles par utilisateur ──────────────────────────────────────
-- Priorité maximale : surpasse les overrides de groupe et les règles globales.
-- Permet d'affiner les droits d'un utilisateur individuel.
CREATE TABLE IF NOT EXISTS user_rule_overrides (
    id             BIGSERIAL   PRIMARY KEY,
    client_user_id BIGINT      NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
    rule_id        BIGINT      NOT NULL REFERENCES filter_rules(id)  ON DELETE CASCADE,
    action         TEXT        NOT NULL CHECK (action IN ('block', 'allow')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_user_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_uro_user ON user_rule_overrides (client_user_id);
CREATE INDEX IF NOT EXISTS idx_uro_rule ON user_rule_overrides (rule_id);

-- ── Droits ────────────────────────────────────────────────────────────────────
GRANT SELECT, INSERT, UPDATE, DELETE ON client_groups       TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON client_users        TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON group_rule_overrides TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_rule_overrides  TO hibou;
GRANT USAGE, SELECT ON SEQUENCE client_groups_id_seq        TO hibou;
GRANT USAGE, SELECT ON SEQUENCE client_users_id_seq         TO hibou;
GRANT USAGE, SELECT ON SEQUENCE group_rule_overrides_id_seq TO hibou;
GRANT USAGE, SELECT ON SEQUENCE user_rule_overrides_id_seq  TO hibou;

-- ── Données initiales ─────────────────────────────────────────────────────────
INSERT INTO client_groups (name, description) VALUES
    ('Défaut',      'Groupe par défaut — applique les règles globales sans modification'),
    ('Administrateurs', 'Accès étendu — peut accéder aux sites normalement bloqués'),
    ('Restreint',   'Accès limité — restrictions supplémentaires')
ON CONFLICT (name) DO NOTHING;