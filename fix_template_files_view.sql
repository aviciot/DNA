-- Recreate v_template_files_with_details view
-- ==============================================
SET search_path TO dna_app, public;

-- Drop if exists (in case it's broken)
DROP VIEW IF EXISTS dna_app.v_template_files_with_details CASCADE;

-- Recreate with correct structure
CREATE OR REPLACE VIEW dna_app.v_template_files_with_details AS
SELECT
    tf.id,
    tf.filename,
    tf.original_filename,
    tf.file_path,
    tf.file_size_bytes,
    tf.description,
    tf.status,
    tf.uploaded_at,
    u.email as uploaded_by_email,
    -- Count of built templates from this file (using new templates table)
    COUNT(DISTINCT t.id) as built_templates_count
FROM dna_app.template_files tf
LEFT JOIN auth.users u ON tf.uploaded_by = u.id
LEFT JOIN dna_app.templates t ON tf.id = t.template_file_id
WHERE tf.status = 'uploaded'
GROUP BY tf.id, u.email
ORDER BY tf.uploaded_at DESC;

-- Verify it works
SELECT id, original_filename, status, built_templates_count
FROM dna_app.v_template_files_with_details
LIMIT 5;

\echo ''
\echo '✅ View recreated successfully!'
\echo ''
