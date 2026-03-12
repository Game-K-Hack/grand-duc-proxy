-- migration_v12 : système de rôles et permissions granulaires
-- Remplace le champ role (admin/viewer) par un système de rôles configurables

CREATE TABLE IF NOT EXISTS roles (
    id          BIGSERIAL    PRIMARY KEY,
    name        TEXT         NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT         NOT NULL DEFAULT '{}',
    is_builtin  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Rôle Administrateur (toutes les permissions)
INSERT INTO roles (name, description, permissions, is_builtin) VALUES (
    'Administrateur',
    'Accès complet à toutes les fonctionnalités',
    '{"dashboard.read":true,"rules.read":true,"rules.write":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_groups.write":true,"client_users.read":true,"client_users.write":true,"test_access.use":true,"users.read":true,"users.write":true,"tls_bypass.read":true,"tls_bypass.write":true,"killswitch.read":true,"killswitch.write":true,"certificates.read":true,"certificates.write":true,"settings.smtp.read":true,"settings.smtp.write":true,"settings.rmm.read":true,"settings.rmm.write":true,"roles.read":true,"roles.write":true,"proxy.restart":true}',
    TRUE
) ON CONFLICT (name) DO NOTHING;

-- Rôle Lecteur (permissions de lecture uniquement)
INSERT INTO roles (name, description, permissions, is_builtin) VALUES (
    'Lecteur',
    'Consultation en lecture seule',
    '{"dashboard.read":true,"rules.read":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_users.read":true,"users.read":true,"tls_bypass.read":true,"killswitch.read":true,"certificates.read":true,"settings.smtp.read":true,"settings.rmm.read":true,"roles.read":true}',
    TRUE
) ON CONFLICT (name) DO NOTHING;

-- Ajout de la colonne role_id sur users
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id BIGINT REFERENCES roles(id);

-- Migration des données existantes
UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'Administrateur') WHERE role = 'admin';
UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'Lecteur')        WHERE role = 'viewer';
UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'Lecteur')        WHERE role_id IS NULL;
