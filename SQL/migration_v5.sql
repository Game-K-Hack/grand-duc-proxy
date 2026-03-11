-- Migration V5 : groupe par défaut
-- À exécuter en tant que superuser PostgreSQL

-- 1. Ajout de la colonne is_default
ALTER TABLE client_groups ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Contrainte : un seul groupe par défaut autorisé
CREATE UNIQUE INDEX IF NOT EXISTS client_groups_one_default
    ON client_groups (is_default) WHERE is_default = TRUE;

-- 3. Créer le groupe par défaut s'il n'existe pas encore
INSERT INTO client_groups (name, description, is_default)
VALUES ('Défaut', 'Appliqué à tous les utilisateurs sans groupe explicite et aux IP inconnues', TRUE)
ON CONFLICT DO NOTHING;

-- 4. Droits
GRANT SELECT, INSERT, UPDATE, DELETE ON client_groups TO hibou;
