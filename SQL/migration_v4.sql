-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v4
-- Passage en many-to-many utilisateurs ↔ groupes
-- psql -U hibou -d grand_duc -f migration_v4.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Supprime les anciennes tables de la v3 (si elles existent) ───────────────
DROP TABLE IF EXISTS user_rule_overrides   CASCADE;
DROP TABLE IF EXISTS group_rule_overrides  CASCADE;
DROP TABLE IF EXISTS client_users          CASCADE;
DROP TABLE IF EXISTS client_groups         CASCADE;

-- ── Groupes ───────────────────────────────────────────────────────────────────
CREATE TABLE client_groups (
    id          BIGSERIAL   PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Utilisateurs (identifiés par IP) ─────────────────────────────────────────
-- Plus de group_id ici : relation many-to-many via client_user_groups
CREATE TABLE client_users (
    id          BIGSERIAL   PRIMARY KEY,
    ip_address  TEXT        NOT NULL UNIQUE,
    label       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_client_users_ip ON client_users (ip_address);

-- ── Table de jonction utilisateurs ↔ groupes (many-to-many) ──────────────────
CREATE TABLE client_user_groups (
    user_id     BIGINT NOT NULL REFERENCES client_users  (id) ON DELETE CASCADE,
    group_id    BIGINT NOT NULL REFERENCES client_groups (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

CREATE INDEX idx_cug_user  ON client_user_groups (user_id);
CREATE INDEX idx_cug_group ON client_user_groups (group_id);

-- ── Association règle ↔ groupe (avec action spécifique au groupe) ─────────────
-- Un groupe peut activer n'importe quelle règle globale avec une action
-- différente de l'action globale de la règle (ex : règle globale=block,
-- le groupe "Directeurs" l'active en allow → accès autorisé pour ce groupe).
CREATE TABLE group_rules (
    id         BIGSERIAL   PRIMARY KEY,
    group_id   BIGINT      NOT NULL REFERENCES client_groups (id) ON DELETE CASCADE,
    rule_id    BIGINT      NOT NULL REFERENCES filter_rules  (id) ON DELETE CASCADE,
    action     TEXT        NOT NULL CHECK (action IN ('block','allow')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (group_id, rule_id)
);

CREATE INDEX idx_gr_group ON group_rules (group_id);
CREATE INDEX idx_gr_rule  ON group_rules (rule_id);

-- ── Droits ────────────────────────────────────────────────────────────────────
GRANT SELECT, INSERT, UPDATE, DELETE ON client_groups      TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON client_users       TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON client_user_groups TO hibou;
GRANT SELECT, INSERT, UPDATE, DELETE ON group_rules        TO hibou;
GRANT USAGE, SELECT ON SEQUENCE client_groups_id_seq  TO hibou;
GRANT USAGE, SELECT ON SEQUENCE client_users_id_seq   TO hibou;
GRANT USAGE, SELECT ON SEQUENCE group_rules_id_seq    TO hibou;

-- ── Données initiales ─────────────────────────────────────────────────────────
INSERT INTO client_groups (name, description) VALUES
    ('Défaut',          'Applique les règles globales sans modification'),
    ('Administrateurs', 'Accès étendu — règles de blocage désactivées'),
    ('Restreint',       'Accès limité — restrictions supplémentaires')
ON CONFLICT (name) DO NOTHING;