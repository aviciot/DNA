BEGIN;

-- 0. Drop orphaned table (only used by unregistered template_analysis.py route)
DROP TABLE IF EXISTS dna_app.template_iso_standards;

-- 1. Add placeholder_dictionary column to iso_standards (master dictionary per standard)
ALTER TABLE dna_app.iso_standards
ADD COLUMN IF NOT EXISTS placeholder_dictionary JSONB DEFAULT '[]';

-- 2. Create per-plan dictionary table (populated when customer plan is created)
CREATE TABLE IF NOT EXISTS dna_app.iso_placeholder_dictionary (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    key         VARCHAR(255) NOT NULL,
    question    TEXT,
    label       VARCHAR(255),
    category    VARCHAR(100) DEFAULT 'General',
    hint        TEXT,
    data_type   VARCHAR(50) DEFAULT 'text',
    is_required BOOLEAN DEFAULT TRUE,
    UNIQUE (plan_id, key)
);

CREATE INDEX IF NOT EXISTS idx_iso_placeholder_dict_plan
ON dna_app.iso_placeholder_dictionary(plan_id);

COMMIT;
