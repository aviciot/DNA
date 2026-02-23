-- ============================================================================
-- Migration 005: AI-Driven Platform Schema
-- ============================================================================
-- Core idea: placeholder is the atomic unit of data collection.
-- One placeholder (e.g. company_name) appears in many documents.
-- Collect it once → fills everywhere.
-- Tasks, emails, chat, portal are just collection channels for placeholders.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. customer_profile_data
--    Single source of truth for all known facts about a customer.
--    Feeds into all documents automatically.
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_profile_data (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    field_key       VARCHAR(255) NOT NULL,   -- e.g. 'company_name', 'ceo_name', 'logo_url'
    field_value     TEXT,                    -- text answer
    file_path       VARCHAR(1000),           -- for uploads (logo, certificates, etc.)
    file_mime_type  VARCHAR(100),
    data_type       VARCHAR(50) NOT NULL DEFAULT 'text',  -- text | file | image | date | number
    source          VARCHAR(50) NOT NULL DEFAULT 'manual', -- manual | email | chat | portal | ai_inferred
    confidence      SMALLINT DEFAULT 100,    -- 0-100, AI inferred values may be lower
    verified        BOOLEAN DEFAULT false,   -- admin confirmed this value
    collected_via_channel_id UUID,           -- FK to collection_requests (set after table created)
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_customer_field UNIQUE (customer_id, field_key)
);

CREATE INDEX idx_profile_data_customer ON dna_app.customer_profile_data(customer_id);
CREATE INDEX idx_profile_data_key ON dna_app.customer_profile_data(field_key);
CREATE INDEX idx_profile_data_verified ON dna_app.customer_profile_data(verified);

COMMENT ON TABLE dna_app.customer_profile_data IS
    'Shared pool of known facts per customer. One entry per field_key. Auto-fills all documents.';
COMMENT ON COLUMN dna_app.customer_profile_data.confidence IS
    '100=confirmed, <100=AI inferred, needs verification';


-- ============================================================================
-- 2. customer_placeholders
--    All unique placeholders required across all of a customer's documents.
--    Derived when a plan is created. Status tracks collection progress.
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_placeholders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id         UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    placeholder_key VARCHAR(255) NOT NULL,   -- e.g. 'company_name', 'ceo_signature'
    display_label   VARCHAR(500),            -- human-readable label for UI/email
    data_type       VARCHAR(50) DEFAULT 'text', -- text | file | image | date | number | signature
    is_required     BOOLEAN DEFAULT true,
    status          VARCHAR(50) DEFAULT 'pending', -- pending | collected | verified | skipped
    profile_data_id UUID REFERENCES dna_app.customer_profile_data(id) ON DELETE SET NULL,
    -- which templates/documents need this placeholder
    template_ids    UUID[],                  -- array of template UUIDs that use this placeholder
    collected_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_customer_plan_placeholder UNIQUE (customer_id, plan_id, placeholder_key)
);

CREATE INDEX idx_placeholders_customer ON dna_app.customer_placeholders(customer_id);
CREATE INDEX idx_placeholders_plan ON dna_app.customer_placeholders(plan_id);
CREATE INDEX idx_placeholders_status ON dna_app.customer_placeholders(status);
CREATE INDEX idx_placeholders_key ON dna_app.customer_placeholders(placeholder_key);

COMMENT ON TABLE dna_app.customer_placeholders IS
    'All unique placeholders needed for a customer plan. Linked to profile_data when collected.';


-- ============================================================================
-- 3. collection_requests
--    A request to collect one or more placeholders via a specific channel.
--    The scheduler creates these. One request = one email/chat session/portal prompt.
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.collection_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id             UUID REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    channel             VARCHAR(50) NOT NULL,  -- email | chat | portal | manual
    status              VARCHAR(50) DEFAULT 'pending', -- pending | sent | responded | expired | cancelled
    placeholder_keys    TEXT[] NOT NULL,       -- which placeholders this request is asking for
    -- email specific
    email_to            VARCHAR(255),
    email_subject       VARCHAR(500),
    email_body          TEXT,
    email_thread_id     VARCHAR(500),          -- to match reply back to this request
    -- ai context
    ai_prompt_used      TEXT,                  -- what the AI generated to ask
    ai_parsed_response  JSONB,                 -- AI's extraction from the reply
    -- scheduling
    scheduled_at        TIMESTAMP,
    sent_at             TIMESTAMP,
    responded_at        TIMESTAMP,
    expires_at          TIMESTAMP,
    reminder_count      SMALLINT DEFAULT 0,
    next_reminder_at    TIMESTAMP,
    created_by          INTEGER REFERENCES auth.users(id),
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_collection_requests_customer ON dna_app.collection_requests(customer_id);
CREATE INDEX idx_collection_requests_status ON dna_app.collection_requests(status);
CREATE INDEX idx_collection_requests_channel ON dna_app.collection_requests(channel);
CREATE INDEX idx_collection_requests_thread ON dna_app.collection_requests(email_thread_id);
CREATE INDEX idx_collection_requests_scheduled ON dna_app.collection_requests(scheduled_at)
    WHERE status = 'pending';

COMMENT ON TABLE dna_app.collection_requests IS
    'Scheduler-managed requests to collect placeholder data via email/chat/portal.';
COMMENT ON COLUMN dna_app.collection_requests.email_thread_id IS
    'Used to match inbound email replies back to this request.';


-- ============================================================================
-- 4. Now add FK from customer_profile_data → collection_requests
-- ============================================================================
ALTER TABLE dna_app.customer_profile_data
    ADD CONSTRAINT profile_data_channel_fkey
    FOREIGN KEY (collected_via_channel_id)
    REFERENCES dna_app.collection_requests(id)
    ON DELETE SET NULL;


-- ============================================================================
-- 5. Patch customer_tasks
--    Add: placeholder_key, answer, answered_at, answered_via
--    These are the missing fields that make tasks actually useful for automation.
-- ============================================================================
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS placeholder_key  VARCHAR(255),  -- which {{placeholder}} this task fills
    ADD COLUMN IF NOT EXISTS answer           TEXT,          -- the collected answer
    ADD COLUMN IF NOT EXISTS answer_file_path VARCHAR(1000), -- for file/image answers
    ADD COLUMN IF NOT EXISTS answered_at      TIMESTAMP,
    ADD COLUMN IF NOT EXISTS answered_via     VARCHAR(50),   -- email | chat | portal | manual | ai
    ADD COLUMN IF NOT EXISTS collection_request_id UUID
        REFERENCES dna_app.collection_requests(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_customer_tasks_placeholder
    ON dna_app.customer_tasks(placeholder_key);
CREATE INDEX IF NOT EXISTS idx_customer_tasks_answered
    ON dna_app.customer_tasks(answered_at)
    WHERE answered_at IS NOT NULL;

COMMENT ON COLUMN dna_app.customer_tasks.placeholder_key IS
    'Which {{placeholder}} in the template this task is collecting data for.';
COMMENT ON COLUMN dna_app.customer_tasks.answer IS
    'The collected answer. Written to customer_profile_data and document content on completion.';


-- ============================================================================
-- 6. Patch customer_documents
--    Add: placeholder_fill_status JSONB to track per-placeholder fill state
--    This lets us know exactly which placeholders are still empty in each doc.
-- ============================================================================
ALTER TABLE dna_app.customer_documents
    ADD COLUMN IF NOT EXISTS placeholder_fill_status JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_auto_filled_at TIMESTAMP;

COMMENT ON COLUMN dna_app.customer_documents.placeholder_fill_status IS
    'Map of placeholder_key → {status: filled|empty|skipped, source: profile|manual|ai}';
COMMENT ON COLUMN dna_app.customer_documents.last_auto_filled_at IS
    'Last time AI auto-filled placeholders from customer_profile_data.';


-- ============================================================================
-- 7. scheduler_jobs
--    The smart scheduler tracks what needs to happen and when.
--    Rules-based: send email, send reminder, escalate, auto-fill from profile.
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.scheduler_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type        VARCHAR(100) NOT NULL, -- send_collection_email | send_reminder | auto_fill | escalate | generate_document
    status          VARCHAR(50) DEFAULT 'pending', -- pending | running | done | failed | skipped
    customer_id     INTEGER REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id         UUID REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    collection_request_id UUID REFERENCES dna_app.collection_requests(id) ON DELETE CASCADE,
    payload         JSONB,                 -- job-specific data
    run_at          TIMESTAMP NOT NULL,    -- when to execute
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    error_message   TEXT,
    retry_count     SMALLINT DEFAULT 0,
    max_retries     SMALLINT DEFAULT 3,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scheduler_jobs_run_at ON dna_app.scheduler_jobs(run_at)
    WHERE status = 'pending';
CREATE INDEX idx_scheduler_jobs_customer ON dna_app.scheduler_jobs(customer_id);
CREATE INDEX idx_scheduler_jobs_status ON dna_app.scheduler_jobs(status);
CREATE INDEX idx_scheduler_jobs_type ON dna_app.scheduler_jobs(job_type);

COMMENT ON TABLE dna_app.scheduler_jobs IS
    'AI scheduler job queue. Drives email sends, reminders, auto-fill, document generation.';


COMMIT;
