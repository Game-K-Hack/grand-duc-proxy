-- migration_v16 : suivi des IP tournantes des postes clients
--
-- Jusqu'ici l'adresse IP ÉTAIT l'identité du poste (client_users.ip_address
-- NOT NULL UNIQUE, jointure des logs par IP, lookup RMM par IP). Dès qu'une IP
-- tournait : poste fantôme dans la liste, perte des droits, et surtout
-- réécriture rétroactive de l'historique — les accès d'hier se retrouvaient
-- attribués au poste qui détient l'IP aujourd'hui.
--
-- Désormais `client_users.id` est l'identité, l'IP est un attribut daté :
--   * client_user_ips        → périodes de détention (qui, quelle IP, de quand à quand)
--   * access_logs.client_user_id → le poste figé au moment de la requête
--
-- Ce fichier est REJOUABLE : docker-init-db.sh l'exécute avec ON_ERROR_STOP=0,
-- une instruction en échec passerait silencieusement. D'où le bloc RAISE NOTICE
-- final, seul signal visible de bonne exécution dans `docker compose logs db`.

-- ── 1. Historique des adresses IP ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS client_user_ips (
  id          BIGSERIAL   PRIMARY KEY,
  user_id     BIGINT      NOT NULL REFERENCES client_users(id) ON DELETE CASCADE,
  ip_address  TEXT        NOT NULL,
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  released_at TIMESTAMPTZ,                              -- NULL = période en cours
  source      TEXT        NOT NULL DEFAULT 'manual',    -- manual | rmm | discover | migration
  note        TEXT,
  CONSTRAINT client_user_ips_period_check
    CHECK (released_at IS NULL OR released_at >= assigned_at)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON client_user_ips TO hibou;
GRANT USAGE, SELECT ON SEQUENCE client_user_ips_id_seq TO hibou;

-- Une IP n'a qu'un seul détenteur actif à un instant donné. C'est cet index
-- qui fait tout le travail, y compris sous concurrence : une course devient
-- une IntegrityError que le backend traduit en 409.
CREATE UNIQUE INDEX IF NOT EXISTS ux_client_user_ips_active_ip
  ON client_user_ips (ip_address) WHERE released_at IS NULL;

-- Un poste n'a qu'une période courante — miroir de client_users.ip_address.
CREATE UNIQUE INDEX IF NOT EXISTS ux_client_user_ips_active_user
  ON client_user_ips (user_id) WHERE released_at IS NULL;

-- « Qui détenait cette IP à l'instant T ? »
CREATE INDEX IF NOT EXISTS ix_client_user_ips_ip_time
  ON client_user_ips (ip_address, assigned_at DESC);

-- Affichage de l'historique dans la fiche du poste.
CREATE INDEX IF NOT EXISTS ix_client_user_ips_user_time
  ON client_user_ips (user_id, assigned_at DESC);

-- ── 2. Un poste peut exister sans IP ────────────────────────────────────────
-- Indispensable pour transférer une IP d'un poste A vers un poste B sans jamais
-- supprimer A — donc sans lui faire perdre ses groupes, son historique et ses
-- logs. Le UNIQUE est conservé : PostgreSQL autorise plusieurs NULL.

ALTER TABLE client_users ALTER COLUMN ip_address DROP NOT NULL;

-- ── 3. Rattachement direct des logs au poste ────────────────────────────────

ALTER TABLE access_logs ADD COLUMN IF NOT EXISTS client_user_id BIGINT;

-- ON DELETE SET NULL et non CASCADE : supprimer un poste ne doit jamais
-- supprimer des lignes de journal.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_access_logs_client_user'
  ) THEN
    ALTER TABLE access_logs
      ADD CONSTRAINT fk_access_logs_client_user
        FOREIGN KEY (client_user_id)
        REFERENCES client_users(id)
        ON DELETE SET NULL;
  END IF;
END$$;

-- ── 4. Amorçage de l'historique pour les postes existants ───────────────────
-- Le NOT EXISTS rend l'insertion rejouable et empêche de rouvrir une période
-- pour un poste qui en a déjà une en cours.

INSERT INTO client_user_ips (user_id, ip_address, assigned_at, source, note)
SELECT cu.id, cu.ip_address, cu.created_at, 'migration', 'Amorçage v16'
  FROM client_users cu
 WHERE cu.ip_address IS NOT NULL
   AND NOT EXISTS (
         SELECT 1 FROM client_user_ips h
          WHERE h.user_id = cu.id AND h.released_at IS NULL
       );

-- ── 5. Backfill des logs existants ──────────────────────────────────────────
-- Rattachement au détenteur ACTUEL de l'IP : c'est la seule information
-- disponible sur le stock antérieur, et elle est exacte tant qu'aucune IP n'a
-- encore tourné — ce qui est le cas avant cette migration.
--
-- Le `client_user_id IS NULL` rend l'UPDATE rejouable ET protège les
-- rattachements déjà établis : après quelques changements d'IP, la vérité en
-- base est plus fine que ce que cette requête produirait.
--
-- Au-delà de quelques millions de lignes, remplacer par une boucle par lots
-- (ctid IN (SELECT ctid … LIMIT 50000)) pour éviter un WAL et un lock massifs.

UPDATE access_logs al
   SET client_user_id = cu.id
  FROM client_users cu
 WHERE al.client_user_id IS NULL
   AND cu.ip_address IS NOT NULL
   AND al.client_ip = cu.ip_address;

-- Index créé APRÈS le backfill, pour ne pas le maintenir pendant l'UPDATE.
-- Sert la vue « tous les logs de ce poste, du plus récent au plus ancien ».
CREATE INDEX IF NOT EXISTS ix_access_logs_client_user_id
  ON access_logs (client_user_id, accessed_at DESC);

ANALYZE client_user_ips;
ANALYZE access_logs;

-- ── 6. Compte rendu ─────────────────────────────────────────────────────────

DO $$
DECLARE
  v_periodes   BIGINT;
  v_rattaches  BIGINT;
  v_orphelins  BIGINT;
  v_incoherent BIGINT;
BEGIN
  SELECT count(*) INTO v_periodes  FROM client_user_ips WHERE released_at IS NULL;
  SELECT count(*) FILTER (WHERE client_user_id IS NOT NULL),
         count(*) FILTER (WHERE client_user_id IS NULL)
    INTO v_rattaches, v_orphelins FROM access_logs;
  SELECT count(*) INTO v_incoherent
    FROM client_users cu
    LEFT JOIN client_user_ips h ON h.user_id = cu.id AND h.released_at IS NULL
   WHERE cu.ip_address IS DISTINCT FROM h.ip_address;

  RAISE NOTICE 'v16 OK : % periodes courantes, % logs rattaches, % logs orphelins, % incoherences',
    v_periodes, v_rattaches, v_orphelins, v_incoherent;

  IF v_incoherent > 0 THEN
    RAISE WARNING 'v16 : % poste(s) dont ip_address ne correspond pas a la periode ouverte', v_incoherent;
  END IF;
END$$;
