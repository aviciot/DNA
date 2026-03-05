-- ============================================================
-- Migration 002: Email Automation System
-- Run with: docker compose exec dna-postgres psql -U dna_user -d dna -f /migrations/002_automation.sql
-- Safe to re-run (all IF NOT EXISTS)
-- ============================================================

SET search_path TO dna_app;

-- ─────────────────────────────────────────────────────────────
-- automation_config  (singleton row — always id=1)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dna_app.automation_config (
    id                          INTEGER PRIMARY KEY DEFAULT 1,
    -- email provider
    email_provider              VARCHAR(50)  DEFAULT 'gmail',       -- gmail | sendgrid
    sendgrid_api_key            TEXT,
    sendgrid_from_email         TEXT,
    sendgrid_from_name          TEXT         DEFAULT 'DNA Compliance',
    gmail_address               TEXT,
    gmail_app_password          TEXT,
    imap_host                   VARCHAR(255) DEFAULT 'imap.gmail.com',
    imap_port                   INTEGER      DEFAULT 993,
    imap_poll_interval_seconds  INTEGER      DEFAULT 60,
    -- LLM for extraction  (re-uses same providers as main ai_settings)
    extraction_provider         VARCHAR(50)  DEFAULT 'gemini',
    extraction_model            VARCHAR(100),
    -- confidence thresholds
    auto_apply_threshold        NUMERIC(3,2) DEFAULT 0.85,
    confidence_floor            NUMERIC(3,2) DEFAULT 0.60,
    review_mode                 VARCHAR(20)  DEFAULT 'hybrid',       -- hybrid | human_first | autonomous
    -- follow-up scheduling
    followup_delay_days         INTEGER      DEFAULT 2,
    max_followups               INTEGER      DEFAULT 3,
    send_window_start           TIME         DEFAULT '09:00',
    send_window_end             TIME         DEFAULT '17:00',
    timezone                    VARCHAR(50)  DEFAULT 'UTC',
    -- feature flag
    enabled                     BOOLEAN      DEFAULT false,
    updated_at                  TIMESTAMP    DEFAULT now()
);

INSERT INTO dna_app.automation_config (id) VALUES (1) ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- email_collection_requests  (one per outbound campaign)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dna_app.email_collection_requests (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         INTEGER     NOT NULL,
    plan_id             UUID        NOT NULL,
    token               VARCHAR(64) UNIQUE NOT NULL,    -- embedded in Reply-To +token
    campaign_number     INTEGER     DEFAULT 1,          -- 1=initial, 2=first follow-up, …
    parent_request_id   UUID        REFERENCES dna_app.email_collection_requests(id),
    questions_snapshot  JSONB,      -- [{placeholder_key, question, hint, example_value}]
    evidence_snapshot   JSONB,      -- [{task_id, title, description}]
    sent_to             TEXT[],     -- all email addresses used
    subject             TEXT,
    status              VARCHAR(50) DEFAULT 'pending', -- pending|partial|completed|expired|failed
    sent_at             TIMESTAMP,
    expires_at          TIMESTAMP,
    created_by          INTEGER,
    created_at          TIMESTAMP   DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ecr_customer  ON dna_app.email_collection_requests(customer_id);
CREATE INDEX IF NOT EXISTS idx_ecr_token     ON dna_app.email_collection_requests(token);
CREATE INDEX IF NOT EXISTS idx_ecr_plan      ON dna_app.email_collection_requests(plan_id);
CREATE INDEX IF NOT EXISTS idx_ecr_status    ON dna_app.email_collection_requests(status);

-- ─────────────────────────────────────────────────────────────
-- email_inbound_log  (every incoming email we process)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dna_app.email_inbound_log (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_request_id   UUID        REFERENCES dna_app.email_collection_requests(id),
    customer_id             INTEGER,
    from_email              TEXT,
    subject                 TEXT,
    body_text               TEXT,
    body_html               TEXT,
    attachments             JSONB       DEFAULT '[]',  -- [{filename, content_type, size_bytes, storage_path}]
    ai_task_id              UUID,
    extraction_result       JSONB,      -- raw LLM output
    status                  VARCHAR(50) DEFAULT 'received', -- received|processing|extracted|applied|failed|skipped
    received_at             TIMESTAMP   DEFAULT now(),
    processed_at            TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eil_customer  ON dna_app.email_inbound_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_eil_request   ON dna_app.email_inbound_log(collection_request_id);
CREATE INDEX IF NOT EXISTS idx_eil_status    ON dna_app.email_inbound_log(status);

-- ─────────────────────────────────────────────────────────────
-- email_extraction_items  (per-answer extracted by AI)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dna_app.email_extraction_items (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_log_id      UUID        NOT NULL REFERENCES dna_app.email_inbound_log(id),
    customer_id         INTEGER     NOT NULL,
    plan_id             UUID,
    item_type           VARCHAR(20) NOT NULL,  -- answer | evidence
    placeholder_key     VARCHAR(255),           -- for answer type
    task_id             UUID,                   -- for evidence type
    extracted_value     TEXT,
    confidence          NUMERIC(4,3),           -- 0.000–1.000
    reasoning           TEXT,
    status              VARCHAR(50) DEFAULT 'pending', -- pending|accepted|rejected|applied|auto_applied
    reviewed_by         INTEGER,
    reviewed_at         TIMESTAMP,
    applied_at          TIMESTAMP,
    created_at          TIMESTAMP   DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eei_log       ON dna_app.email_extraction_items(inbound_log_id);
CREATE INDEX IF NOT EXISTS idx_eei_status    ON dna_app.email_extraction_items(status);
CREATE INDEX IF NOT EXISTS idx_eei_customer  ON dna_app.email_extraction_items(customer_id);
CREATE INDEX IF NOT EXISTS idx_eei_key       ON dna_app.email_extraction_items(placeholder_key);

-- done
SELECT 'Automation tables created/verified' AS result;
