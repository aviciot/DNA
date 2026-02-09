-- Migration 006: Template Versions & History
-- ============================================
-- Adds version tracking and change history for templates

SET search_path TO dna_app, public;

\echo ''
\echo '📦 Migration 006: Adding template version history...'
\echo ''

-- 1. Add version tracking columns to templates table
\echo '1. Adding version tracking to templates table...'

ALTER TABLE dna_app.templates
ADD COLUMN IF NOT EXISTS version_number INTEGER DEFAULT 1 NOT NULL,
ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS last_edited_by INTEGER REFERENCES auth.users(id);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_templates_last_edited ON dna_app.templates(last_edited_at DESC);

\echo '   ✓ Version tracking columns added'

-- 2. Create template_versions table for history
\echo '2. Creating template_versions table...'

CREATE TABLE IF NOT EXISTS dna_app.template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES dna_app.templates(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    template_structure JSONB NOT NULL,
    change_summary TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES auth.users(id),

    -- Ensure unique version numbers per template
    CONSTRAINT unique_template_version UNIQUE (template_id, version_number)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_template_versions_template ON dna_app.template_versions(template_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_template_versions_created ON dna_app.template_versions(created_at DESC);

\echo '   ✓ template_versions table created'

-- 3. Create initial version entries for existing templates
\echo '3. Creating initial version entries for existing templates...'

INSERT INTO dna_app.template_versions (
    template_id,
    version_number,
    template_structure,
    change_summary,
    created_at,
    created_by
)
SELECT
    id,
    1,
    template_structure,
    'Initial version created by AI Builder',
    created_at,
    NULL -- AI-created, no user
FROM dna_app.templates
WHERE NOT EXISTS (
    SELECT 1 FROM dna_app.template_versions
    WHERE template_versions.template_id = templates.id
);

\echo '   ✓ Initial versions created'

-- 4. Create view for templates with version info
\echo '4. Creating v_templates_with_versions view...'

CREATE OR REPLACE VIEW dna_app.v_templates_with_versions AS
SELECT
    t.id,
    t.name,
    t.description,
    t.iso_standard,
    t.template_file_id,
    t.template_structure,
    t.status,
    t.version_number,
    t.total_fixed_sections,
    t.total_fillable_sections,
    t.semantic_tags,
    t.created_at,
    t.updated_at,
    t.approved_at,
    t.last_edited_at,
    t.last_edited_by,
    u_edited.email as last_edited_by_email,
    COUNT(DISTINCT tv.id) as total_versions
FROM dna_app.templates t
LEFT JOIN auth.users u_edited ON t.last_edited_by = u_edited.id
LEFT JOIN dna_app.template_versions tv ON t.id = tv.template_id
GROUP BY t.id, u_edited.email;

\echo '   ✓ View created'

-- 5. Grant permissions
\echo '5. Granting permissions...'

GRANT SELECT, INSERT, UPDATE, DELETE ON dna_app.template_versions TO dna_user;
GRANT SELECT ON dna_app.v_templates_with_versions TO dna_user;

\echo '   ✓ Permissions granted'

-- 6. Verify
\echo ''
\echo '📊 Verification:'
SELECT
    (SELECT COUNT(*) FROM dna_app.templates) as templates_count,
    (SELECT COUNT(*) FROM dna_app.template_versions) as versions_count;

\echo ''
\echo '✅ Migration 006 complete! Template version history is ready.'
\echo '   - Templates now track version_number and last_edited_at'
\echo '   - template_versions table stores full history'
\echo '   - Initial versions created for existing templates'
\echo ''
