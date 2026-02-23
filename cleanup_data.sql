-- Full Data Cleanup - Keep Structure, Remove Old Data (CORRECTED ORDER)
-- =====================================================
SET search_path TO dna_app, public;

\echo '🧹 Starting full data cleanup...'
\echo ''

-- 1. Clear AI tasks FIRST (they reference template_files)
\echo '1. Clearing old AI tasks...'
DELETE FROM dna_app.ai_tasks;

-- 2. Clear templates
\echo '2. Clearing templates...'
DELETE FROM dna_app.templates;

-- 3. Clear template-ISO mappings
\echo '3. Clearing template-ISO mappings...'
DELETE FROM dna_app.template_iso_mapping;

-- 4. Clear customer responses
\echo '4. Clearing customer responses...'
DELETE FROM dna_app.customer_responses;

-- 5. Clear generated documents
\echo '5. Clearing generated documents...'
DELETE FROM dna_app.generated_documents;

-- 6. Clear old template files (after AI tasks cleared)
\echo '6. Clearing old template files...'
DELETE FROM dna_app.template_files;

-- 7. Keep ISO standards
\echo '7. ISO standards kept (not deleted)'
\echo ''

-- Show what's left
\echo '📊 Current state after cleanup:'
\echo ''
SELECT 'Templates' as table_name, COUNT(*) as count FROM dna_app.templates
UNION ALL
SELECT 'Template Files', COUNT(*) FROM dna_app.template_files
UNION ALL
SELECT 'AI Tasks', COUNT(*) FROM dna_app.ai_tasks
UNION ALL
SELECT 'ISO Standards', COUNT(*) FROM dna_app.iso_standards;

\echo ''
\echo '✅ Full cleanup complete! Database is clean and ready.'
\echo '🚀 Now upload your ISMS documents fresh!'
\echo ''
