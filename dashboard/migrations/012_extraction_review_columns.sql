-- Migration 012: Add rejected_reason column to email_extraction_items
-- Supports the enhanced reject flow: rejected | pending | on_hold
-- Run: docker compose exec dna-postgres psql -U dna_user -d dna -f /migrations/012_extraction_review_columns.sql

ALTER TABLE dna_app.email_extraction_items
    ADD COLUMN IF NOT EXISTS rejected_reason TEXT;

SELECT 'Migration 012 complete — rejected_reason column added' AS result;
