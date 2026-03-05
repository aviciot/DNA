-- Migration 013: Extraction reply config flag + human review task flag
-- 2026-03-04

-- Add extraction reply toggle to global automation config
ALTER TABLE dna_app.automation_config
    ADD COLUMN IF NOT EXISTS send_extraction_reply BOOLEAN DEFAULT TRUE;

-- Add human review flag columns to customer_tasks
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS needs_human_review BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS human_review_reason TEXT;
