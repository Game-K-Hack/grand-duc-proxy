-- migration_v17 : permissions du système de mise à jour
--
-- Ajoute `updates.read` et `updates.apply` aux deux rôles built-in.
--
-- Rappel n°1 : docker-init-db.sh exécute ce fichier avec ON_ERROR_STOP=0 — une
-- instruction en échec passerait silencieusement, d'où le RAISE NOTICE final.
--
-- Rappel n°2 : ce fichier n'est joué qu'à la CRÉATION du volume PostgreSQL.
-- Sur une installation existante, c'est le runner backend/services/migrations.py
-- qui l'applique au démarrage, et _ensure_builtin_roles() (backend/main.py) qui
-- réconcilie les permissions de toute façon. Les trois sont volontaires : cette
-- migration n'est qu'une ceinture en plus des bretelles.

UPDATE roles
   SET permissions = '{"dashboard.read":true,"rules.read":true,"rules.write":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_groups.write":true,"client_users.read":true,"client_users.write":true,"test_access.use":true,"users.read":true,"users.write":true,"tls_bypass.read":true,"tls_bypass.write":true,"killswitch.read":true,"killswitch.write":true,"certificates.read":true,"certificates.write":true,"settings.smtp.read":true,"settings.smtp.write":true,"settings.templates.read":true,"settings.templates.write":true,"settings.appearance.read":true,"settings.appearance.write":true,"settings.rmm.read":true,"settings.rmm.write":true,"roles.read":true,"roles.write":true,"proxy.restart":true,"updates.read":true,"updates.apply":true}'
 WHERE name = 'Administrateur' AND is_builtin = TRUE;

UPDATE roles
   SET permissions = '{"dashboard.read":true,"rules.read":true,"logs.read":true,"proxy_logs.read":true,"client_groups.read":true,"client_users.read":true,"users.read":true,"tls_bypass.read":true,"killswitch.read":true,"certificates.read":true,"settings.smtp.read":true,"settings.templates.read":true,"settings.appearance.read":true,"settings.rmm.read":true,"roles.read":true,"updates.read":true}'
 WHERE name = 'Lecteur' AND is_builtin = TRUE;

DO $$
DECLARE
  v_admin  BOOLEAN;
  v_viewer BOOLEAN;
BEGIN
  SELECT (permissions::json->>'updates.apply')::boolean INTO v_admin
    FROM roles WHERE name = 'Administrateur' AND is_builtin = TRUE;
  SELECT (permissions::json->>'updates.read')::boolean INTO v_viewer
    FROM roles WHERE name = 'Lecteur' AND is_builtin = TRUE;
  RAISE NOTICE 'v17 OK : Administrateur.updates.apply=%, Lecteur.updates.read=%',
    COALESCE(v_admin, FALSE), COALESCE(v_viewer, FALSE);
END$$;
