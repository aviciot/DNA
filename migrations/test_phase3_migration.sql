-- =====================================================
-- Phase 3A - Migration Testing Script
-- =====================================================

\echo '==== TEST 1: Verify New Tables Created ===='
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'dna_app'
AND table_name IN (
    'customer_configuration',
    'task_resolutions',
    'task_templates',
    'v_customer_iso_progress'
)
ORDER BY table_name;
-- Expected: 3 tables + 1 view

\echo ''
\echo '==== TEST 2: Verify Columns Added to customer_tasks ===='
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'dna_app'
AND table_name = 'customer_tasks'
AND column_name IN (
    'is_ignored',
    'ignored_at',
    'ignored_by',
    'ignore_reason',
    'created_manually_by',
    'manual_task_context'
)
ORDER BY column_name;
-- Expected: 6 rows

\echo ''
\echo '==== TEST 3: Verify stand_alone ISO Standard ===='
SELECT id, code, name, active
FROM dna_app.iso_standards
WHERE code = 'stand_alone';
-- Expected: 1 row with UUID 00000000-0000-0000-0000-000000000001

\echo ''
\echo '==== TEST 4: Verify Default Configuration Templates ===='
SELECT config_type, config_key, is_default, is_active
FROM dna_app.customer_configuration
WHERE customer_id IS NULL
ORDER BY config_type;
-- Expected: 3 rows (welcome_email, evidence_request, assignment_notification)

\echo ''
\echo '==== TEST 5: Verify Task Templates ===='
SELECT template_name, task_type, task_scope, is_system_template
FROM dna_app.task_templates
WHERE is_system_template = true
ORDER BY template_name;
-- Expected: 7 rows

\echo ''
\echo '==== TEST 6: Check Email Template Variables ===='
SELECT
    config_type,
    config_key,
    jsonb_array_length(template_variables) as variable_count,
    template_variables
FROM dna_app.customer_configuration
WHERE is_template = true
ORDER BY config_type;
-- Expected: Variable arrays defined for each template

\echo ''
\echo '==== TEST 7: Verify View Works ===='
SELECT COUNT(*) as plan_count
FROM dna_app.v_customer_iso_progress;
-- Expected: Should not error (count may be 0 if no plans exist yet)

\echo ''
\echo '==== TEST 8: Test stand_alone ISO in Constraint ===='
-- This should work (stand_alone is allowed)
SELECT 'stand_alone code constraint: OK' as test_result
WHERE EXISTS (
    SELECT 1 FROM dna_app.iso_standards WHERE code = 'stand_alone'
);
-- Expected: OK

\echo ''
\echo '==== TEST 9: Check Existing Customers Still Work ===='
SELECT id, name, email, status
FROM dna_app.customers
ORDER BY created_at DESC
LIMIT 5;
-- Expected: Should return existing customers without error

\echo ''
\echo '==== TEST 10: Check Existing Tasks Still Work ===='
SELECT id, customer_id, task_type, status, auto_generated
FROM dna_app.customer_tasks
ORDER BY created_at DESC
LIMIT 5;
-- Expected: Should return existing tasks without error

\echo ''
\echo '========================================='
\echo 'Migration Verification Tests Complete!'
\echo '========================================='
