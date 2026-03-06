-- Migration 004: Customer Portal
-- Creates portal_activity_log table and portal_user with minimal grants

-- Activity log (INSERT only for portal_user)
CREATE TABLE IF NOT EXISTS dna_app.portal_activity_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event       VARCHAR(100) NOT NULL,
    token       VARCHAR(64),
    customer_id INTEGER,
    detail      JSONB       DEFAULT '{}',
    ip_address  TEXT,
    created_at  TIMESTAMP   DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pal_customer  ON dna_app.portal_activity_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_pal_token     ON dna_app.portal_activity_log(token);
CREATE INDEX IF NOT EXISTS idx_pal_event     ON dna_app.portal_activity_log(event);
CREATE INDEX IF NOT EXISTS idx_pal_created   ON dna_app.portal_activity_log(created_at DESC);

-- Portal DB user with minimal grants
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal_user') THEN
        CREATE USER portal_user WITH PASSWORD 'portal_user';
    END IF;
END$$;

GRANT CONNECT ON DATABASE dna TO portal_user;
GRANT USAGE ON SCHEMA dna_app TO portal_user;

-- Read access
GRANT SELECT ON dna_app.email_collection_requests TO portal_user;
GRANT SELECT ON dna_app.customer_tasks TO portal_user;
GRANT SELECT ON dna_app.customers TO portal_user;
GRANT SELECT ON dna_app.customer_iso_plans TO portal_user;
GRANT SELECT ON dna_app.iso_standards TO portal_user;

-- Write access (scoped)
GRANT UPDATE (answer, answered_via, answered_at, status, updated_at,
              evidence_uploaded, evidence_files) ON dna_app.customer_tasks TO portal_user;
GRANT INSERT, UPDATE ON dna_app.customer_profile_data TO portal_user;
GRANT SELECT, INSERT ON dna_app.portal_activity_log TO portal_user;

-- Sequences needed for inserts
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dna_app TO portal_user;
