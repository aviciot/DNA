-- Migration 005: Rename tables to follow customer_ prefix convention
-- task_templates     → customer_task_templates   (exists)
-- task_resolutions   → customer_task_resolutions (create if missing)
-- collection_channels→ customer_collection_channels (create if missing)

BEGIN;

-- ─── task_templates → customer_task_templates ────────────────────────────────

ALTER TABLE dna_app.task_templates RENAME TO customer_task_templates;

ALTER TABLE dna_app.customer_task_templates RENAME CONSTRAINT task_templates_pkey            TO customer_task_templates_pkey;
ALTER TABLE dna_app.customer_task_templates RENAME CONSTRAINT task_templates_created_by_fkey TO customer_task_templates_created_by_fkey;

ALTER INDEX dna_app.idx_task_template_active RENAME TO idx_customer_task_templates_active;
ALTER INDEX dna_app.idx_task_template_scope  RENAME TO idx_customer_task_templates_scope;
ALTER INDEX dna_app.idx_task_template_type   RENAME TO idx_customer_task_templates_type;


-- ─── customer_task_resolutions (was never created — create it now) ────────────

CREATE TABLE IF NOT EXISTS dna_app.customer_task_resolutions (
    id                  uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id             uuid NOT NULL REFERENCES dna_app.customer_tasks(id) ON DELETE CASCADE,
    resolution_type     varchar(50) NOT NULL,
    resolution_data     jsonb,
    is_final            boolean DEFAULT false,
    requires_approval   boolean DEFAULT false,
    approved_at         timestamp without time zone,
    approved_by         integer REFERENCES auth.users(id),
    quality_score       integer CHECK (quality_score BETWEEN 1 AND 5),
    completeness_score  integer CHECK (completeness_score BETWEEN 0 AND 100),
    resolved_by         integer REFERENCES auth.users(id),
    resolved_at         timestamp without time zone DEFAULT now(),
    follow_up_required  boolean DEFAULT false,
    follow_up_task_id   uuid REFERENCES dna_app.customer_tasks(id),
    notes               text,
    attachments         jsonb
);

CREATE INDEX IF NOT EXISTS idx_customer_task_resolutions_task
    ON dna_app.customer_task_resolutions(task_id);
CREATE INDEX IF NOT EXISTS idx_customer_task_resolutions_type
    ON dna_app.customer_task_resolutions(resolution_type);
CREATE INDEX IF NOT EXISTS idx_customer_task_resolutions_requires_approval
    ON dna_app.customer_task_resolutions(requires_approval) WHERE requires_approval = true;


-- ─── customer_collection_channels (was never created — create it now) ─────────

CREATE TABLE IF NOT EXISTS dna_app.customer_collection_channels (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    customer_id      integer NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id          uuid REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    channel_type     varchar(50) NOT NULL,
    channel_config   jsonb DEFAULT '{}',
    share_token      varchar(100) UNIQUE,
    token_expires_at timestamptz,
    is_active        boolean DEFAULT true,
    created_by       integer REFERENCES auth.users(id),
    created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customer_collection_channels_customer
    ON dna_app.customer_collection_channels(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_collection_channels_token
    ON dna_app.customer_collection_channels(share_token) WHERE share_token IS NOT NULL;

COMMIT;
