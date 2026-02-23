-- =====================================================
-- Phase 3A - Functional Testing Script
-- Tests the new features with actual data operations
-- =====================================================

BEGIN;

\echo '==== FUNCTIONAL TEST 1: Create Custom Configuration for Customer ===='
-- Create a custom welcome email for a specific customer
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    template_variables,
    created_by
)
SELECT
    c.id,  -- Use first customer
    'welcome_email',
    'custom_welcome_test',
    '{"subject": "Custom Welcome {{company_name}}!", "body": "Dear {{primary_contact}}, this is a custom test..."}'::jsonb,
    true,
    '[{"name": "company_name", "type": "string"}, {"name": "primary_contact", "type": "string"}]'::jsonb,
    1
FROM dna_app.customers c
LIMIT 1;

-- Verify it was created
SELECT
    'Custom config created' as test_result,
    config_type,
    config_key,
    customer_id IS NOT NULL as is_customer_specific
FROM dna_app.customer_configuration
WHERE config_key = 'custom_welcome_test';
-- Expected: 1 row, is_customer_specific = true

\echo ''
\echo '==== FUNCTIONAL TEST 2: Create Manual Task from Template ===='
-- Create a manual task using the "Schedule Kickoff Meeting" template
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    auto_generated,
    created_manually_by,
    manual_task_context,
    status,
    due_date
)
SELECT
    c.id,  -- Use first customer
    tt.task_type,
    tt.task_scope,
    REPLACE(tt.default_title, '{{company_name}}', c.name),
    tt.default_description,
    tt.default_priority,
    false,  -- Manual task
    1,      -- Admin user
    'Test manual task creation',
    'pending',
    CURRENT_DATE + (tt.default_due_in_days || ' days')::INTERVAL
FROM dna_app.customers c, dna_app.task_templates tt
WHERE tt.template_name = 'Schedule Kickoff Meeting'
LIMIT 1
RETURNING id, title, task_scope, auto_generated, created_manually_by;
-- Expected: 1 task created with auto_generated = false

\echo ''
\echo '==== FUNCTIONAL TEST 3: Mark Task as Ignored ===='
-- Create a test task first
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    status,
    auto_generated
)
SELECT
    c.id,
    'test',
    'customer',
    'Test task to be ignored',
    'pending',
    true
FROM dna_app.customers c
LIMIT 1
RETURNING id as task_id;

-- Mark it as ignored
UPDATE dna_app.customer_tasks
SET
    is_ignored = true,
    ignored_at = NOW(),
    ignored_by = 1,
    ignore_reason = 'Template removed during testing'
WHERE title = 'Test task to be ignored'
RETURNING id, title, is_ignored, ignore_reason;
-- Expected: Task marked as ignored

\echo ''
\echo '==== FUNCTIONAL TEST 4: Test Task Resolution - Answer Provided ===='
-- Submit an answer resolution
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    resolved_by
)
SELECT
    ct.id,
    'answer_provided',
    '{"answer": "Test Answer Corporation", "question_placeholder": "company_name"}'::jsonb,
    true,
    1
FROM dna_app.customer_tasks ct
WHERE ct.auto_generated = false
  AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
LIMIT 1
RETURNING id, task_id, resolution_type, is_final;
-- Expected: 1 resolution created

\echo ''
\echo '==== FUNCTIONAL TEST 5: Test Task Resolution - Evidence Upload ===='
-- Submit evidence resolution (requires approval)
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    requires_approval,
    resolved_by
)
SELECT
    ct.id,
    'evidence_uploaded',
    '{"file_path": "/test/evidence.pdf", "file_name": "evidence.pdf", "file_size": 123456}'::jsonb,
    false,  -- Not final until approved
    true,   -- Requires approval
    1
FROM dna_app.customer_tasks ct
WHERE ct.auto_generated = false
  AND (ct.is_ignored = false OR ct.is_ignored IS NULL)
LIMIT 1
RETURNING id, task_id, resolution_type, requires_approval, is_final;
-- Expected: 1 resolution created, requires_approval = true

\echo ''
\echo '==== FUNCTIONAL TEST 6: Approve Resolution ===='
-- Approve the evidence resolution
UPDATE dna_app.task_resolutions
SET
    is_final = true,
    approved_at = NOW(),
    approved_by = 1,
    quality_score = 5,
    completeness_score = 100
WHERE resolution_type = 'evidence_uploaded'
  AND requires_approval = true
RETURNING id, is_final, approved_at IS NOT NULL as approved, quality_score;
-- Expected: Resolution approved

\echo ''
\echo '==== FUNCTIONAL TEST 7: Create ISO Plan with stand_alone ===='
-- Create a plan using the stand_alone ISO
INSERT INTO dna_app.customer_iso_plans (
    customer_id,
    iso_standard_id,
    plan_name,
    plan_status,
    created_by
)
SELECT
    c.id,
    '00000000-0000-0000-0000-000000000001'::UUID,  -- stand_alone ISO
    'Test Stand-alone Templates Plan',
    'active',
    1
FROM dna_app.customers c
LIMIT 1
RETURNING id, plan_name, iso_standard_id;
-- Expected: Plan created with stand_alone ISO

\echo ''
\echo '==== FUNCTIONAL TEST 8: Mark ISO Plan as Ignored ===='
-- Mark the test plan as ignored
UPDATE dna_app.customer_iso_plans
SET
    is_ignored = true,
    ignored_at = NOW(),
    ignored_by = 1,
    ignore_reason = 'Test plan no longer needed'
WHERE plan_name = 'Test Stand-alone Templates Plan'
RETURNING id, plan_name, is_ignored, ignore_reason;
-- Expected: Plan marked as ignored

\echo ''
\echo '==== FUNCTIONAL TEST 9: Test Progress View with Ignored Tasks ===='
-- Check that progress view excludes ignored tasks
SELECT
    'Progress View Test' as test_name,
    COUNT(*) FILTER (WHERE is_ignored = false OR is_ignored IS NULL) as active_tasks,
    COUNT(*) FILTER (WHERE is_ignored = true) as ignored_tasks_excluded
FROM dna_app.customer_tasks ct
WHERE customer_id IN (SELECT DISTINCT customer_id FROM dna_app.customer_iso_plans LIMIT 1);
-- Expected: Ignored tasks are counted separately

\echo ''
\echo '==== FUNCTIONAL TEST 10: Update Task Template Usage ===='
-- Increment usage count for a template
UPDATE dna_app.task_templates
SET
    usage_count = usage_count + 1,
    last_used_at = NOW()
WHERE template_name = 'Schedule Kickoff Meeting'
RETURNING template_name, usage_count, last_used_at IS NOT NULL as last_used_updated;
-- Expected: Usage count incremented

\echo ''
\echo '==== FUNCTIONAL TEST 11: Query Configuration with Variables ===='
-- Get welcome email and show available variables
SELECT
    config_type,
    config_key,
    config_value->>'subject' as email_subject,
    jsonb_array_length(template_variables) as num_variables,
    (SELECT jsonb_agg(v->>'name') FROM jsonb_array_elements(template_variables) v) as variable_names
FROM dna_app.customer_configuration
WHERE config_type = 'welcome_email'
  AND is_default = true;
-- Expected: Show subject and list of variable names

\echo ''
\echo '==== FUNCTIONAL TEST 12: Test Resolution Quality Scoring ===='
-- Add quality scores to resolutions
UPDATE dna_app.task_resolutions
SET
    quality_score = 4,
    completeness_score = 85
WHERE resolution_type = 'answer_provided'
RETURNING id, resolution_type, quality_score, completeness_score;
-- Expected: Scores updated

\echo ''
\echo '==== VERIFICATION: Count All Test Data Created ===='
SELECT
    'Configurations created' as category,
    COUNT(*) as count
FROM dna_app.customer_configuration
WHERE config_key LIKE '%test%'
UNION ALL
SELECT
    'Manual tasks created',
    COUNT(*)
FROM dna_app.customer_tasks
WHERE created_manually_by IS NOT NULL
UNION ALL
SELECT
    'Tasks ignored',
    COUNT(*)
FROM dna_app.customer_tasks
WHERE is_ignored = true
UNION ALL
SELECT
    'Resolutions created',
    COUNT(*)
FROM dna_app.task_resolutions
UNION ALL
SELECT
    'Plans with stand_alone ISO',
    COUNT(*)
FROM dna_app.customer_iso_plans
WHERE iso_standard_id = '00000000-0000-0000-0000-000000000001'::UUID;

\echo ''
\echo '========================================='
\echo 'Functional Tests Complete!'
\echo '========================================='

-- ROLLBACK all test data
ROLLBACK;

\echo ''
\echo 'Test data rolled back (no changes committed)'
