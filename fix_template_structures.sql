-- Fix existing template structures to include all required fields
-- Run this to add missing fields to templates created before the fix

DO $$
DECLARE
    template_record RECORD;
    old_structure JSONB;
    new_structure JSONB;
    fillable_sections JSONB;
    semantic_tags TEXT[];
BEGIN
    -- Loop through all templates
    FOR template_record IN
        SELECT id, name, template_structure, template_file_id
        FROM dna_app.templates
    LOOP
        old_structure := template_record.template_structure;

        -- Check if structure is missing required fields
        IF old_structure ? 'document_title' THEN
            -- Already has the fields, skip
            RAISE NOTICE 'Template % already has complete structure', template_record.id;
            CONTINUE;
        END IF;

        -- Extract fillable_sections
        fillable_sections := old_structure->'fillable_sections';

        -- Extract all semantic tags
        SELECT ARRAY_AGG(DISTINCT tag)
        INTO semantic_tags
        FROM jsonb_array_elements(fillable_sections) AS section,
             jsonb_array_elements_text(section->'semantic_tags') AS tag;

        -- Build new complete structure
        new_structure := jsonb_build_object(
            'document_title', template_record.name,
            'fixed_sections', '[]'::jsonb,
            'fillable_sections', COALESCE(fillable_sections, '[]'::jsonb),
            'metadata', jsonb_build_object(
                'source_file', 'legacy',
                'parsed_at', NOW()::text,
                'total_fixed_sections', 0,
                'total_fillable_sections', jsonb_array_length(COALESCE(fillable_sections, '[]'::jsonb)),
                'semantic_tags_used', COALESCE(semantic_tags, ARRAY[]::TEXT[])
            )
        );

        -- Update template
        UPDATE dna_app.templates
        SET
            template_structure = new_structure,
            total_fixed_sections = 0,
            total_fillable_sections = jsonb_array_length(COALESCE(fillable_sections, '[]'::jsonb)),
            semantic_tags = semantic_tags,
            updated_at = NOW()
        WHERE id = template_record.id;

        RAISE NOTICE 'Updated template: % (%)', template_record.name, template_record.id;
    END LOOP;

    RAISE NOTICE 'Migration complete!';
END $$;
