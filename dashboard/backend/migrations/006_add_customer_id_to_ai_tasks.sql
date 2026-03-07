-- Add customer_id to ai_tasks and ai_usage_log for per-customer LLM cost tracking

ALTER TABLE dna_app.ai_tasks
    ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES dna_app.customers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_ai_tasks_customer ON dna_app.ai_tasks(customer_id);

ALTER TABLE dna_app.ai_usage_log
    ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES dna_app.customers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_ai_usage_log_customer ON dna_app.ai_usage_log(customer_id);
