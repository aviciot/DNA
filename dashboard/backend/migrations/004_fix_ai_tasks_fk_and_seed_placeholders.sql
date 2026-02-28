-- ============================================================
-- Fix 1: ai_tasks.template_file_id FK — preserve history on delete
-- ============================================================
ALTER TABLE dna_app.ai_tasks
    DROP CONSTRAINT IF EXISTS ai_tasks_template_file_id_fkey;

ALTER TABLE dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_template_file_id_fkey
    FOREIGN KEY (template_file_id)
    REFERENCES dna_app.template_files(id)
    ON DELETE SET NULL;

-- ============================================================
-- Fix 2: customer_placeholders — add missing columns for questionnaire
-- ============================================================
ALTER TABLE dna_app.customer_placeholders
    ADD COLUMN IF NOT EXISTS question       text,
    ADD COLUMN IF NOT EXISTS category       varchar(100) DEFAULT 'General',
    ADD COLUMN IF NOT EXISTS hint           text,
    ADD COLUMN IF NOT EXISTS example_value  text,
    ADD COLUMN IF NOT EXISTS semantic_tags  text[] DEFAULT '{}';

-- ============================================================
-- Fix 3: customer_profile_data — add display_label
-- ============================================================
ALTER TABLE dna_app.customer_profile_data
    ADD COLUMN IF NOT EXISTS display_label varchar(500);

-- ============================================================
-- Fix 4: collection_channels table (Phase 1 share_link support)
-- ============================================================
CREATE TABLE IF NOT EXISTS dna_app.collection_channels (
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

CREATE INDEX IF NOT EXISTS idx_collection_channels_customer
    ON dna_app.collection_channels(customer_id);
CREATE INDEX IF NOT EXISTS idx_collection_channels_token
    ON dna_app.collection_channels(share_token) WHERE share_token IS NOT NULL;
