-- migration_v10 : intégration RMM + enrichissement client_users

-- Table des intégrations RMM
CREATE TABLE IF NOT EXISTS rmm_integrations (
  id                    BIGSERIAL    PRIMARY KEY,
  name                  TEXT         NOT NULL,
  type                  VARCHAR(30)  NOT NULL,   -- tactical | ninja | datto | atera | connectwise
  url                   TEXT         NOT NULL,
  api_key               TEXT         NOT NULL,
  api_secret            TEXT,                    -- client_secret pour OAuth2 (NinjaRMM, Datto…)
  enabled               BOOLEAN      NOT NULL DEFAULT TRUE,
  sync_interval_minutes INTEGER      NOT NULL DEFAULT 60,
  last_sync_at          TIMESTAMPTZ,
  last_sync_status      TEXT,
  created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Nouvelles colonnes sur client_users
ALTER TABLE client_users
  ADD COLUMN IF NOT EXISTS hostname          TEXT,
  ADD COLUMN IF NOT EXISTS os               TEXT,
  ADD COLUMN IF NOT EXISTS source           TEXT        NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS rmm_agent_id     TEXT,
  ADD COLUMN IF NOT EXISTS last_seen_rmm    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS rmm_integration_id BIGINT;

-- Clé étrangère (ajoutée après la création de la table cible)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_client_users_rmm_integration'
  ) THEN
    ALTER TABLE client_users
      ADD CONSTRAINT fk_client_users_rmm_integration
        FOREIGN KEY (rmm_integration_id)
        REFERENCES rmm_integrations(id)
        ON DELETE SET NULL;
  END IF;
END$$;
