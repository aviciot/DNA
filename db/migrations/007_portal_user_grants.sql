-- Migration 007: Fix portal_user grants for answer submission trigger chain
-- The answer flow fires a 3-step trigger cascade:
--   UPDATE customer_tasks
--     -> trg_task_to_placeholder -> UPDATE customer_placeholders
--       -> trg_placeholder_to_document -> SELECT/UPDATE customer_documents
--       -> trg_placeholder_to_task    -> UPDATE customer_tasks
-- Also: INSERT...ON CONFLICT DO UPDATE on customer_profile_data requires SELECT.

-- Trigger chain: customer_placeholders
GRANT SELECT, UPDATE ON dna_app.customer_placeholders TO portal_user;

-- Trigger chain: customer_documents
GRANT SELECT, UPDATE ON dna_app.customer_documents TO portal_user;

-- ON CONFLICT DO UPDATE requires SELECT (INSERT+UPDATE already granted in 004)
GRANT SELECT ON dna_app.customer_profile_data TO portal_user;

-- answered_by_name and completed_at columns used in answer submission
GRANT UPDATE (answered_by_name, completed_at) ON dna_app.customer_tasks TO portal_user;
