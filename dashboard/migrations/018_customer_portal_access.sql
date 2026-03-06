-- Migration 018: Customer Portal Access
-- Decouples portal authentication from email_collection_requests.
-- Portal tokens are now customer-level (created on customer creation),
-- independent of any collection campaign.

-- 1. Create customer_portal_access table
CREATE TABLE IF NOT EXISTS dna_app.customer_portal_access (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  INTEGER     NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    token        VARCHAR(64) UNIQUE NOT NULL,
    expires_at   TIMESTAMP   NOT NULL DEFAULT (NOW() + INTERVAL '1 year'),
    created_at   TIMESTAMP   DEFAULT NOW(),
    last_used_at TIMESTAMP,
    CONSTRAINT uq_cpa_customer UNIQUE (customer_id)
);

CREATE INDEX IF NOT EXISTS idx_cpa_token    ON dna_app.customer_portal_access(token);
CREATE INDEX IF NOT EXISTS idx_cpa_customer ON dna_app.customer_portal_access(customer_id);

-- 2. Grant portal_user access
GRANT SELECT ON dna_app.customer_portal_access TO portal_user;
GRANT UPDATE (last_used_at) ON dna_app.customer_portal_access TO portal_user;

-- 3. Backfill: generate tokens for all existing customers
INSERT INTO dna_app.customer_portal_access (customer_id, token)
SELECT id, md5(random()::text || id::text || clock_timestamp()::text)
       || md5(random()::text || clock_timestamp()::text)
FROM dna_app.customers
ON CONFLICT (customer_id) DO NOTHING;
