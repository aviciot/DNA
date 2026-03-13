-- Index for customer-scoped usage queries (GET /{customer_id}/usage)
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_customer
    ON dna_app.ai_usage_log (customer_id, started_at DESC)
    WHERE customer_id IS NOT NULL;
