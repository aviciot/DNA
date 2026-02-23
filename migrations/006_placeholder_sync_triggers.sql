-- Migration 006: Bidirectional sync triggers
-- placeholder → task (and reverse) stay in sync automatically
-- Covers: collect, revert, edit, auto_fill

-- ============================================================
-- TRIGGER 1: customer_placeholders → customer_tasks
-- Fires on any UPDATE to customer_placeholders.status or profile_data_id
-- ============================================================

CREATE OR REPLACE FUNCTION dna_app.sync_task_from_placeholder()
RETURNS TRIGGER AS $$
BEGIN
    -- Map placeholder status → task status
    UPDATE dna_app.customer_tasks
    SET
        status = CASE NEW.status
            WHEN 'collected'   THEN 'completed'
            WHEN 'auto_filled' THEN 'completed'
            WHEN 'pending'     THEN 'pending'
            ELSE status  -- unknown status: leave as-is
        END,
        completed_at = CASE NEW.status
            WHEN 'collected'   THEN COALESCE(completed_at, now())
            WHEN 'auto_filled' THEN COALESCE(completed_at, now())
            WHEN 'pending'     THEN NULL  -- revert clears completion
            ELSE completed_at
        END,
        updated_at = now()
    WHERE
        customer_id     = NEW.customer_id
        AND plan_id     = NEW.plan_id
        AND placeholder_key = NEW.placeholder_key
        AND status NOT IN ('cancelled');  -- never touch cancelled tasks

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_placeholder_to_task ON dna_app.customer_placeholders;

CREATE TRIGGER trg_placeholder_to_task
    AFTER UPDATE OF status ON dna_app.customer_placeholders
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION dna_app.sync_task_from_placeholder();


-- ============================================================
-- TRIGGER 2: customer_placeholders → customer_documents
-- Updates placeholder_fill_status JSONB and recalculates completion_percentage
-- ============================================================

CREATE OR REPLACE FUNCTION dna_app.sync_document_from_placeholder()
RETURNS TRIGGER AS $$
DECLARE
    doc_record RECORD;
    total_keys INT;
    filled_keys INT;
    new_pct INT;
    new_status VARCHAR(50);
BEGIN
    -- Update every document that uses this template for this customer/plan
    FOR doc_record IN
        SELECT cd.id, cd.placeholder_fill_status, cd.mandatory_sections_total
        FROM dna_app.customer_documents cd
        WHERE cd.customer_id = NEW.customer_id
          AND cd.plan_id     = NEW.plan_id
          AND NEW.template_ids IS NOT NULL
          AND cd.template_id = ANY(NEW.template_ids)
    LOOP
        -- Update the JSONB fill status for this key
        UPDATE dna_app.customer_documents
        SET
            placeholder_fill_status = placeholder_fill_status ||
                jsonb_build_object(
                    NEW.placeholder_key,
                    CASE NEW.status
                        WHEN 'collected'   THEN 'filled'
                        WHEN 'auto_filled' THEN 'filled'
                        WHEN 'pending'     THEN 'pending'
                        ELSE 'pending'
                    END
                ),
            last_auto_filled_at = CASE
                WHEN NEW.status IN ('collected', 'auto_filled') THEN now()
                ELSE last_auto_filled_at
            END,
            updated_at = now()
        WHERE id = doc_record.id;

        -- Recalculate completion_percentage based on filled keys
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE value::text = '"filled"')
        INTO total_keys, filled_keys
        FROM jsonb_each(
            (SELECT placeholder_fill_status FROM dna_app.customer_documents WHERE id = doc_record.id)
        );

        IF total_keys > 0 THEN
            new_pct := ROUND((filled_keys::NUMERIC / total_keys) * 100);
        ELSE
            new_pct := 0;
        END IF;

        new_status := CASE
            WHEN new_pct = 100 THEN 'ready'
            WHEN new_pct > 0   THEN 'in_progress'
            ELSE 'not_started'
        END;

        UPDATE dna_app.customer_documents
        SET
            completion_percentage = new_pct,
            status = new_status
        WHERE id = doc_record.id;

    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_placeholder_to_document ON dna_app.customer_placeholders;

CREATE TRIGGER trg_placeholder_to_document
    AFTER UPDATE OF status ON dna_app.customer_placeholders
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION dna_app.sync_document_from_placeholder();


-- ============================================================
-- TRIGGER 3: customer_tasks → customer_placeholders (reverse)
-- If admin manually completes/reverts a task, placeholder mirrors it
-- ============================================================

CREATE OR REPLACE FUNCTION dna_app.sync_placeholder_from_task()
RETURNS TRIGGER AS $$
BEGIN
    -- Only sync tasks that are linked to a placeholder
    IF NEW.placeholder_key IS NULL OR NEW.plan_id IS NULL THEN
        RETURN NEW;
    END IF;

    UPDATE dna_app.customer_placeholders
    SET
        status = CASE NEW.status
            WHEN 'completed' THEN 'collected'
            WHEN 'pending'   THEN 'pending'
            WHEN 'cancelled' THEN 'pending'  -- cancelled task reopens placeholder
            ELSE status
        END,
        collected_at = CASE NEW.status
            WHEN 'completed' THEN COALESCE(collected_at, now())
            WHEN 'pending'   THEN NULL
            WHEN 'cancelled' THEN NULL
            ELSE collected_at
        END
    WHERE
        customer_id     = NEW.customer_id
        AND plan_id     = NEW.plan_id
        AND placeholder_key = NEW.placeholder_key
        -- Prevent loop: only update if placeholder status would actually change
        AND status IS DISTINCT FROM (
            CASE NEW.status
                WHEN 'completed' THEN 'collected'
                WHEN 'pending'   THEN 'pending'
                WHEN 'cancelled' THEN 'pending'
                ELSE status
            END
        );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_task_to_placeholder ON dna_app.customer_tasks;

CREATE TRIGGER trg_task_to_placeholder
    AFTER UPDATE OF status ON dna_app.customer_tasks
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION dna_app.sync_placeholder_from_task();
