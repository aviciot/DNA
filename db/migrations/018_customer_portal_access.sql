-- Migration 018: Customer-level portal access tokens
-- Decouples portal authentication from email_collection_requests.
-- One long-lived token per customer, created at customer creation time.

CREATE TABLE IF NOT EXISTS dna_app.customer_portal_access (
    id          SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE
                    REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    token       VARCHAR(64) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 year',
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_customer_portal_access_token
    ON dna_app.customer_portal_access(token);

-- Backfill tokens for existing customers (no existing row wins via ON CONFLICT)
INSERT INTO dna_app.customer_portal_access (customer_id, token, expires_at)
SELECT id, encode(gen_random_bytes(32), 'hex'), NOW() + INTERVAL '1 year'
FROM dna_app.customers
ON CONFLICT (customer_id) DO NOTHING;

-- Grant portal_user read access (needed by portal-backend validate_token)
GRANT SELECT, UPDATE ON dna_app.customer_portal_access TO portal_user;
