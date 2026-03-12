-- migration_v11 : préférences de notification et surveillance des règles

-- Préférences par utilisateur (quels événements déclencher un email)
CREATE TABLE IF NOT EXISTS notification_prefs (
  user_id    BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type TEXT    NOT NULL,  -- certificate | proxy_restart | killswitch | new_account | rule_triggered | rmm_sync_error
  enabled    BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (user_id, event_type)
);

-- Règles à surveiller par utilisateur (pour rule_triggered)
CREATE TABLE IF NOT EXISTS notification_rule_watches (
  user_id              BIGINT NOT NULL REFERENCES users(id)         ON DELETE CASCADE,
  rule_id              BIGINT NOT NULL REFERENCES filter_rules(id)  ON DELETE CASCADE,
  last_notified_log_id BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, rule_id)
);
