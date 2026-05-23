-- migration_v15 : suppression de la contrainte CHECK obsolète sur users.role
-- Depuis migration_v12, la colonne texte `role` recopie le NOM du rôle
-- (ex: 'Administrateur', 'Lecteur', ou tout rôle personnalisé) défini dans
-- la table `roles`. L'ancienne contrainte CHECK (role IN ('admin','viewer'))
-- héritée de migration_v2 empêchait toute création/modification d'utilisateur
-- avec un autre nom de rôle (CheckViolationError "users_role_check").

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
