-- Update v_templates_with_details view to include version_number
-- ================================================================
SET search_path TO dna_app, public;

\echo 'Updating v_templates_with_details view to include version_number...'

DROP VIEW IF EXISTS dna_app.v_templates_with_details CASCADE;

CREATE OR REPLACE VIEW dna_app.v_templates_with_details AS
SELECT
    t.id,
    t.name,
    t.description,
    t.iso_standard,
    t.template_file_id,
    t.template_structure,
    t.status,
    t.version,
    t.version_number,
    t.restored_from_version,
    t.total_fixed_sections,
    t.total_fillable_sections,
    t.semantic_tags,
    t.ai_task_id,
    t.created_at,
    t.updated_at,
    t.approved_at,
    t.last_edited_at,
    t.last_edited_by,
    tf.original_filename as source_filename,
    tf.file_path as source_file_path,
    u_created.email as created_by_email,
    u_approved.email as approved_by_email,
    ARRAY_AGG(DISTINCT iso.code) FILTER (WHERE iso.code IS NOT NULL) as iso_codes,
    COUNT(DISTINCT gd.id) as customer_document_count
FROM dna_app.templates t
LEFT JOIN dna_app.template_files tf ON t.template_file_id = tf.id
LEFT JOIN auth.users u_created ON t.created_by = u_created.id
LEFT JOIN auth.users u_approved ON t.approved_by = u_approved.id
LEFT JOIN dna_app.template_iso_mapping tim ON t.id = tim.template_id
LEFT JOIN dna_app.iso_standards iso ON tim.iso_standard_id = iso.id
LEFT JOIN dna_app.generated_documents gd ON t.id = gd.template_id
GROUP BY t.id, tf.original_filename, tf.file_path, u_created.email, u_approved.email;

\echo '✅ View updated successfully with version_number!'
