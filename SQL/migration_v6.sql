-- ─────────────────────────────────────────────────────────────────────────────
-- Grand-Duc — Migration v6 : table tls_bypass (exceptions proxy)
-- psql -U hibou -d grand_duc -f migration_v6.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- Hôtes dont le trafic n'est pas filtré par le proxy.
-- Les sous-domaines sont inclus automatiquement.
CREATE TABLE IF NOT EXISTS tls_bypass (
    id          BIGSERIAL   PRIMARY KEY,
    host        TEXT        NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON tls_bypass    TO hibou;
GRANT USAGE, SELECT ON SEQUENCE tls_bypass_id_seq     TO hibou;

-- Données initiales : Microsoft (anciennement hardcodé dans le proxy)
INSERT INTO tls_bypass (host, description) VALUES
    ('mobile.events.data.microsoft.com', 'Microsoft data'),
    ('events.data.microsoft.com',        'Microsoft data'),
    ('settings-win.data.microsoft.com',  'Microsoft data'),
    ('watson.telemetry.microsoft.com',   'Microsoft telemetry'),
    ('ocsp.digicert.com',    'Digicert ocsp'),
    ('ocsp.pki.goog',        'Pki ocsp'),
    ('ocsp2.globalsign.com', 'Globalsign ocsp2')
ON CONFLICT (host) DO NOTHING;
