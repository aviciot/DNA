-- Migration: Fix Relationships and Enable Proper Cleanup
-- Date: 2024-02-11
-- Purpose:
--   1. Fix FK constraints to allow proper deletion
--   2. Add unique constraint for reference documents (name + version)
--   3. Add many-to-many for templates ↔ ISO standards
--   4. Improve data model consistency

BEGIN;

-- ============================================================================
-- 1. Fix ai_tasks FK to allow CASCADE delete
-- ============================================================================

-- Drop existing FK
ALTER TABLE dna_app.ai_tasks
DROP CONSTRAINT IF EXISTS ai_tasks_template_file_id_fkey;

-- Re-add with CASCADE
ALTER TABLE dna_app.ai_tasks
ADD CONSTRAINT ai_tasks_template_file_id_fkey
FOREIGN KEY (template_file_id)
REFERENCES dna_app.template_files(id)
ON DELETE CASCADE;

-- ============================================================================
-- 2. Add unique constraint for reference documents (name + version)
-- ============================================================================

-- First, add version column if it doesn't have proper default
ALTER TABLE dna_app.template_files
ALTER COLUMN version SET DEFAULT '1.0';

-- Update NULL versions to '1.0'
UPDATE dna_app.template_files
SET version = '1.0'
WHERE version IS NULL;

-- Add unique constraint (filename + version)
ALTER TABLE dna_app.template_files
ADD CONSTRAINT unique_filename_version
UNIQUE (filename, version);

-- ============================================================================
-- 3. Create many-to-many relationship: templates ↔ ISO standards
-- ============================================================================

CREATE TABLE IF NOT EXISTS dna_app.template_iso_standards (
    template_id UUID NOT NULL REFERENCES dna_app.templates(id) ON DELETE CASCADE,
    iso_standard_id UUID NOT NULL REFERENCES dna_app.iso_standards(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (template_id, iso_standard_id)
);

CREATE INDEX IF NOT EXISTS idx_template_iso_template
ON dna_app.template_iso_standards(template_id);

CREATE INDEX IF NOT EXISTS idx_template_iso_standard
ON dna_app.template_iso_standards(iso_standard_id);

-- ============================================================================
-- 4. Add iso_standard_id to template_files (reference docs belong to ISO)
-- ============================================================================

ALTER TABLE dna_app.template_files
ADD COLUMN IF NOT EXISTS iso_standard_id UUID
REFERENCES dna_app.iso_standards(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_template_files_iso_standard
ON dna_app.template_files(iso_standard_id);

-- ============================================================================
-- 5. Add file_type column to distinguish reference docs vs templates
-- ============================================================================

ALTER TABLE dna_app.template_files
ADD COLUMN IF NOT EXISTS file_type VARCHAR(50) DEFAULT 'reference';

ALTER TABLE dna_app.template_files
ADD CONSTRAINT file_type_valid
CHECK (file_type IN ('reference', 'template', 'generated'));

CREATE INDEX IF NOT EXISTS idx_template_files_type
ON dna_app.template_files(file_type);

-- ============================================================================
-- 6. Add cascading delete for templates → template_files
-- ============================================================================

-- This is already SET NULL which is correct - we want to keep the file
-- even if template is deleted (it might be used by other templates)

-- ============================================================================
-- 7. Add soft delete support
-- ============================================================================

-- Add deleted_at column if not exists
ALTER TABLE dna_app.template_files
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- Add deleted_by column
ALTER TABLE dna_app.template_files
ADD COLUMN IF NOT EXISTS deleted_by INTEGER
REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_template_files_deleted
ON dna_app.template_files(deleted_at)
WHERE deleted_at IS NOT NULL;

-- ============================================================================
-- 8. Create view for reference documents only
-- ============================================================================

CREATE OR REPLACE VIEW dna_app.v_reference_documents AS
SELECT
    tf.*,
    iso.code as iso_standard_code,
    iso.name as iso_standard_name,
    u.email as uploaded_by_email,
    COUNT(DISTINCT t.id) as template_count,
    COUNT(DISTINCT at.id) as analysis_count
FROM dna_app.template_files tf
LEFT JOIN dna_app.iso_standards iso ON tf.iso_standard_id = iso.id
LEFT JOIN auth.users u ON tf.uploaded_by = u.id
LEFT JOIN dna_app.templates t ON t.template_file_id = tf.id
LEFT JOIN dna_app.ai_tasks at ON at.template_file_id = tf.id
WHERE tf.file_type = 'reference'
  AND tf.deleted_at IS NULL
GROUP BY tf.id, iso.id, u.email;

-- ============================================================================
-- 9. Create function for safe delete (soft delete)
-- ============================================================================

CREATE OR REPLACE FUNCTION dna_app.soft_delete_template_file(
    p_file_id UUID,
    p_user_id INTEGER
) RETURNS BOOLEAN AS $$
BEGIN
    -- Check if file has dependencies
    IF EXISTS (
        SELECT 1 FROM dna_app.templates
        WHERE template_file_id = p_file_id
        AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot delete: Active templates depend on this file';
    END IF;

    -- Soft delete
    UPDATE dna_app.template_files
    SET
        deleted_at = NOW(),
        deleted_by = p_user_id,
        status = 'deleted'
    WHERE id = p_file_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. Create function for hard delete (with cascade)
-- ============================================================================

CREATE OR REPLACE FUNCTION dna_app.hard_delete_template_file(
    p_file_id UUID,
    p_force BOOLEAN DEFAULT FALSE
) RETURNS BOOLEAN AS $$
DECLARE
    v_template_count INTEGER;
BEGIN
    -- Count active templates
    SELECT COUNT(*) INTO v_template_count
    FROM dna_app.templates
    WHERE template_file_id = p_file_id
    AND status = 'active';

    -- Check if force is required
    IF v_template_count > 0 AND NOT p_force THEN
        RAISE EXCEPTION 'Cannot delete: % active templates depend on this file. Use force=true to delete anyway.', v_template_count;
    END IF;

    -- Delete (cascade will handle ai_tasks)
    DELETE FROM dna_app.template_files
    WHERE id = p_file_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- Verify the changes
-- ============================================================================

-- Show all FK constraints on template_files
\d dna_app.template_files

-- Show many-to-many table
\d dna_app.template_iso_standards

-- Show reference documents view
SELECT * FROM dna_app.v_reference_documents LIMIT 5;
