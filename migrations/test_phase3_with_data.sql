-- =====================================================
-- Phase 3A - Complete Functional Test with Test Data
-- Creates test customer and demonstrates all features
-- =====================================================

BEGIN;

\echo '==== SETUP: Create Test Customer ===='
INSERT INTO dna_app.customers (
    name, email, contact_person, status, created_by
) VALUES (
    'Test Company Inc',
    'test@testcompany.com',
    'John Test',
    'active',
    1
) RETURNING id, name, email;

-- Store customer_id for later use
\set test_customer_id (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')

\echo ''
\echo '==== TEST 1: Create Custom Configuration for Customer ===='
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    template_variables,
    created_by
) VALUES (
    (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com'),
    'welcome_email',
    'custom_test_welcome',
    '{"subject": "Custom Welcome {{company_name}}!", "body": "Dear {{primary_contact}}, welcome to our test..."}'::jsonb,
    true,
    '[{"name": "company_name", "type": "string"}, {"name": "primary_contact", "type": "string"}]'::jsonb,
    1
) RETURNING id, config_type, config_key, customer_id IS NOT NULL as is_customer_specific;

\echo ''
\echo '==== TEST 2: Create ISO Plan with stand_alone ISO ===='
INSERT INTO dna_app.customer_iso_plans (
    customer_id,
    iso_standard_id,
    plan_name,
    plan_status,
    created_by
) VALUES (
    (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com'),
    '00000000-0000-0000-0000-000000000001'::UUID,  -- stand_alone ISO
    'Test Stand-alone Plan',
    'active',
    1
) RETURNING id, plan_name, iso_standard_id::text;

\echo ''
\echo '==== TEST 3: Create Manual Task from Template ===='
WITH template AS (
    SELECT * FROM dna_app.task_templates
    WHERE template_name = 'Schedule Kickoff Meeting'
    LIMIT 1
),
customer AS (
    SELECT id, name FROM dna_app.customers WHERE email = 'test@testcompany.com'
)
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    due_date,
    auto_generated,
    created_manually_by,
    manual_task_context,
    status
)
SELECT
    c.id,
    t.task_type,
    t.task_scope,
    REPLACE(t.default_title, '{{company_name}}', c.name),
    t.default_description,
    t.default_priority,
    CURRENT_DATE + (t.default_due_in_days || ' days')::INTERVAL,
    false,
    1,
    'Test manual task creation',
    'pending'
FROM customer c, template t
RETURNING id, title, task_scope, auto_generated, created_manually_by IS NOT NULL as is_manual;

\echo ''
\echo '==== TEST 4: Create Auto-generated Task ===='
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    status,
    auto_generated,
    requires_evidence
) VALUES (
    (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com'),
    'answer_question',
    'question',
    'What is your organization name?',
    'This will be used throughout compliance documents',
    'high',
    'pending',
    true,
    false
) RETURNING id, title, auto_generated, requires_evidence;

\echo ''
\echo '==== TEST 5: Submit Answer Resolution ===='
WITH task AS (
    SELECT id FROM dna_app.customer_tasks
    WHERE title = 'What is your organization name?'
    LIMIT 1
)
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    resolved_by
)
SELECT
    t.id,
    'answer_provided',
    '{"answer": "Test Company Inc", "question_placeholder": "organization_name"}'::jsonb,
    true,
    1
FROM task t
RETURNING id, task_id, resolution_type, is_final;

\echo ''
\echo '==== TEST 6: Mark Task as Completed ===='
UPDATE dna_app.customer_tasks
SET status = 'completed', completed_at = NOW(), completed_by = 1
WHERE title = 'What is your organization name?'
RETURNING id, title, status, completed_at IS NOT NULL as completed;

\echo ''
\echo '==== TEST 7: Create Evidence Task ===='
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    status,
    auto_generated,
    requires_evidence,
    evidence_description
) VALUES (
    (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com'),
    'upload_evidence',
    'question',
    'Upload backup policy document',
    'Please provide your documented backup policy',
    'medium',
    'pending',
    true,
    true,
    'PDF or Word document showing your backup procedures and schedule'
) RETURNING id, title, requires_evidence, evidence_description;

\echo ''
\echo '==== TEST 8: Submit Evidence Resolution (Needs Approval) ===='
WITH task AS (
    SELECT id FROM dna_app.customer_tasks
    WHERE title = 'Upload backup policy document'
    LIMIT 1
)
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    requires_approval,
    resolved_by
)
SELECT
    t.id,
    'evidence_uploaded',
    '{"file_path": "/uploads/test/backup_policy.pdf", "file_name": "backup_policy.pdf", "file_size": 524288}'::jsonb,
    false,
    true,
    1
FROM task t
RETURNING id, task_id, resolution_type, requires_approval, is_final;

\echo ''
\echo '==== TEST 9: Update Task to Under Review ===='
UPDATE dna_app.customer_tasks
SET status = 'under_review'
WHERE title = 'Upload backup policy document'
RETURNING id, title, status;

\echo ''
\echo '==== TEST 10: Approve Evidence Resolution ===='
WITH resolution AS (
    SELECT tr.id
    FROM dna_app.task_resolutions tr
    JOIN dna_app.customer_tasks ct ON tr.task_id = ct.id
    WHERE ct.title = 'Upload backup policy document'
    AND tr.resolution_type = 'evidence_uploaded'
    LIMIT 1
)
UPDATE dna_app.task_resolutions
SET
    is_final = true,
    approved_at = NOW(),
    approved_by = 1,
    quality_score = 5,
    completeness_score = 100
FROM resolution r
WHERE task_resolutions.id = r.id
RETURNING task_resolutions.id, is_final, approved_at IS NOT NULL as approved, quality_score, completeness_score;

\echo ''
\echo '==== TEST 11: Mark Evidence Task as Completed ===='
UPDATE dna_app.customer_tasks
SET status = 'completed', completed_at = NOW(), completed_by = 1
WHERE title = 'Upload backup policy document'
RETURNING id, title, status;

\echo ''
\echo '==== TEST 12: Create Task to be Ignored ===='
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    status,
    auto_generated
) VALUES (
    (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com'),
    'test_ignore',
    'question',
    'Task to be ignored - template removed',
    'pending',
    true
) RETURNING id, title, status;

\echo ''
\echo '==== TEST 13: Mark Task as Ignored ===='
UPDATE dna_app.customer_tasks
SET
    is_ignored = true,
    ignored_at = NOW(),
    ignored_by = 1,
    ignore_reason = 'Template removed from customer plan during testing'
WHERE title = 'Task to be ignored - template removed'
RETURNING id, title, is_ignored, ignored_at IS NOT NULL as ignored_timestamp_set, ignore_reason;

\echo ''
\echo '==== TEST 14: Query Progress View ===='
SELECT
    c.name as customer_name,
    iso.name as iso_name,
    v.total_tasks,
    v.completed_tasks,
    v.in_progress_tasks,
    v.pending_tasks,
    v.ignored_tasks,
    v.progress_percentage
FROM dna_app.v_customer_iso_progress v
JOIN dna_app.customers c ON v.customer_id = c.id
JOIN dna_app.iso_standards iso ON v.iso_standard_id = iso.id
WHERE c.email = 'test@testcompany.com';

\echo ''
\echo '==== TEST 15: Verify Ignored Tasks Not in Active Count ===='
SELECT
    COUNT(*) FILTER (WHERE is_ignored = false OR is_ignored IS NULL) as active_tasks,
    COUNT(*) FILTER (WHERE is_ignored = true) as ignored_tasks,
    COUNT(*) as total_tasks
FROM dna_app.customer_tasks
WHERE customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com');

\echo ''
\echo '==== TEST 16: Get All Resolutions ===='
SELECT
    ct.title as task_title,
    tr.resolution_type,
    tr.is_final,
    tr.requires_approval,
    tr.approved_at IS NOT NULL as is_approved,
    tr.quality_score,
    tr.completeness_score
FROM dna_app.task_resolutions tr
JOIN dna_app.customer_tasks ct ON tr.task_id = ct.id
WHERE ct.customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')
ORDER BY tr.resolved_at;

\echo ''
\echo '==== TEST 17: Get Welcome Email Template with Variables ===='
SELECT
    config_type,
    config_key,
    config_value->>'subject' as subject,
    jsonb_array_length(template_variables) as num_variables,
    (SELECT jsonb_agg(v->>'name') FROM jsonb_array_elements(template_variables) v) as variables
FROM dna_app.customer_configuration
WHERE config_type = 'welcome_email'
  AND is_default = true;

\echo ''
\echo '==== TEST 18: Update Task Template Usage ===='
UPDATE dna_app.task_templates
SET usage_count = usage_count + 1, last_used_at = NOW()
WHERE template_name = 'Schedule Kickoff Meeting'
RETURNING template_name, usage_count, last_used_at::date as last_used_date;

\echo ''
\echo '==== SUMMARY: All Test Data Created ===='
SELECT
    'Total Customers' as item,
    COUNT(*)::text as count
FROM dna_app.customers
WHERE email LIKE '%test%'
UNION ALL
SELECT
    'Total Tasks (Active)',
    COUNT(*)::text
FROM dna_app.customer_tasks
WHERE customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')
  AND (is_ignored = false OR is_ignored IS NULL)
UNION ALL
SELECT
    'Total Tasks (Ignored)',
    COUNT(*)::text
FROM dna_app.customer_tasks
WHERE customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')
  AND is_ignored = true
UNION ALL
SELECT
    'Total Resolutions',
    COUNT(*)::text
FROM dna_app.task_resolutions tr
JOIN dna_app.customer_tasks ct ON tr.task_id = ct.id
WHERE ct.customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')
UNION ALL
SELECT
    'Total Configurations',
    COUNT(*)::text
FROM dna_app.customer_configuration
WHERE customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com')
UNION ALL
SELECT
    'Total ISO Plans',
    COUNT(*)::text
FROM dna_app.customer_iso_plans
WHERE customer_id = (SELECT id FROM dna_app.customers WHERE email = 'test@testcompany.com');

\echo ''
\echo '========================================='
\echo 'All Functional Tests Complete!'
\echo '========================================='

-- ROLLBACK to clean up test data
ROLLBACK;

\echo ''
\echo 'Test data rolled back (no changes persisted)'
