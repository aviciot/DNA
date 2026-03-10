-- Migration 021: task_execution_log
-- Operational audit table — one row per send attempt for any outbound task.
-- Keeps customer_tasks clean (business-level) while providing full delivery history.

CREATE TABLE IF NOT EXISTS dna_app.task_execution_log (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id        UUID        NOT NULL REFERENCES dna_app.customer_tasks(id) ON DELETE CASCADE,
    attempt_number INT         NOT NULL DEFAULT 1,
    status         VARCHAR(20) NOT NULL,   -- 'attempted' | 'succeeded' | 'failed'
    email_address  TEXT,                   -- recipient address used
    error_message  TEXT,                   -- SMTP / LLM error detail if failed
    metadata       JSONB       DEFAULT '{}', -- provider, model, smtp_response, etc.
    attempted_at   TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tel_task     ON dna_app.task_execution_log(task_id);
CREATE INDEX IF NOT EXISTS idx_tel_status   ON dna_app.task_execution_log(status);
CREATE INDEX IF NOT EXISTS idx_tel_attempted ON dna_app.task_execution_log(attempted_at DESC);
