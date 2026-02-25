-- Data fix: ISO 27001:2022 had templates from multiple uploads merged into one ISO plan
-- due to ON CONFLICT DO UPDATE reusing the same iso_standards row.
-- This script keeps only the LATEST iso_standards row and removes all templates
-- linked to older duplicate rows.

DO $$
DECLARE
    latest_id  UUID;
    old_ids    UUID[];
BEGIN
    -- Find the latest iso_standards row for ISO 27001:2022 (en)
    SELECT id INTO latest_id
    FROM dna_app.iso_standards
    WHERE code = 'ISO 27001:2022' AND language = 'en'
    ORDER BY created_at DESC
    LIMIT 1;

    IF latest_id IS NULL THEN
        RAISE NOTICE 'No ISO 27001:2022 row found, nothing to fix.';
        RETURN;
    END IF;

    -- Collect all OTHER rows for the same code+language
    SELECT ARRAY(
        SELECT id FROM dna_app.iso_standards
        WHERE code = 'ISO 27001:2022' AND language = 'en'
          AND id <> latest_id
    ) INTO old_ids;

    IF array_length(old_ids, 1) IS NULL THEN
        RAISE NOTICE 'Only one ISO 27001:2022 row exists — checking for duplicate templates on it.';
    ELSE
        RAISE NOTICE 'Found % duplicate iso_standards rows to remove.', array_length(old_ids, 1);

        -- Delete template_iso_mapping for templates linked to old iso rows
        DELETE FROM dna_app.template_iso_mapping
        WHERE iso_standard_id = ANY(old_ids);

        -- Delete templates whose ai_task_id belongs to tasks pointing at old iso rows
        DELETE FROM dna_app.templates
        WHERE ai_task_id IN (
            SELECT id FROM dna_app.ai_tasks
            WHERE iso_standard_id = ANY(old_ids)
        );

        -- Delete old iso_standards rows
        DELETE FROM dna_app.iso_standards
        WHERE id = ANY(old_ids);

        RAISE NOTICE 'Removed duplicate iso_standards rows and their templates.';
    END IF;

    -- Now deduplicate templates on the surviving row:
    -- Keep only the LATEST set (by ai_task_id created_at) — remove earlier task's templates
    WITH ranked_tasks AS (
        SELECT DISTINCT t.ai_task_id,
               at2.created_at,
               ROW_NUMBER() OVER (ORDER BY at2.created_at DESC) AS rn
        FROM dna_app.templates t
        JOIN dna_app.template_iso_mapping tim ON tim.template_id = t.id
        JOIN dna_app.ai_tasks at2 ON at2.id = t.ai_task_id
        WHERE tim.iso_standard_id = latest_id
    ),
    old_tasks AS (
        SELECT ai_task_id FROM ranked_tasks WHERE rn > 1
    )
    DELETE FROM dna_app.template_iso_mapping
    WHERE template_id IN (
        SELECT id FROM dna_app.templates WHERE ai_task_id IN (SELECT ai_task_id FROM old_tasks)
    );

    WITH ranked_tasks AS (
        SELECT DISTINCT t.ai_task_id,
               at2.created_at,
               ROW_NUMBER() OVER (ORDER BY at2.created_at DESC) AS rn
        FROM dna_app.templates t
        JOIN dna_app.ai_tasks at2 ON at2.id = t.ai_task_id
        WHERE t.iso_standard = 'ISO 27001:2022'
          AND t.ai_task_id IN (
              SELECT id FROM dna_app.ai_tasks WHERE iso_standard_id = latest_id
          )
    ),
    old_tasks AS (
        SELECT ai_task_id FROM ranked_tasks WHERE rn > 1
    )
    DELETE FROM dna_app.templates
    WHERE ai_task_id IN (SELECT ai_task_id FROM old_tasks);

    RAISE NOTICE 'Data fix complete. Surviving iso_standards id: %', latest_id;
END $$;
