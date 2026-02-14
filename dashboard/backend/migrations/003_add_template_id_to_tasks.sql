-- ============================================================================
-- Migration 003: Add template_id to customer_tasks
-- ============================================================================
-- Purpose: Link tasks to the specific template that generated them
-- Impact: Enables accurate task grouping by template in customer workspace
-- ============================================================================

-- Step 1: Add template_id column (nullable initially for existing data)
ALTER TABLE dna_app.customer_tasks
ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES dna_app.templates(id) ON DELETE CASCADE;

-- Step 2: Create index for performance
CREATE INDEX IF NOT EXISTS idx_customer_tasks_template ON dna_app.customer_tasks(template_id);

-- Step 3: Add comment
COMMENT ON COLUMN dna_app.customer_tasks.template_id IS 'Template that generated this task (NULL for customer/plan-level tasks)';

-- Step 4: Backfill existing tasks with template_id
-- For tasks that have plan_id but no template_id, try to infer from plan templates
UPDATE dna_app.customer_tasks ct
SET template_id = (
    SELECT cipt.template_id
    FROM dna_app.customer_iso_plan_templates cipt
    WHERE cipt.plan_id = ct.plan_id
    LIMIT 1  -- If multiple templates, pick first one (admin can correct manually)
)
WHERE ct.plan_id IS NOT NULL
  AND ct.template_id IS NULL
  AND ct.task_scope IN ('document', 'question');  -- Only backfill template-related tasks

-- Step 5: Log results
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO updated_count
    FROM dna_app.customer_tasks
    WHERE template_id IS NOT NULL;

    RAISE NOTICE 'Migration 003 complete: % tasks now have template_id', updated_count;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
