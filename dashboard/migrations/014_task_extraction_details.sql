-- Migration 014: Add extraction detail columns to customer_tasks
-- extraction_confidence  — LLM confidence score (0-1) when the answer/evidence was extracted
-- extraction_reasoning   — LLM reasoning / what it recognized from the content
-- reviewed_by_human      — TRUE when an operator manually verified or approved the data

ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS extraction_confidence FLOAT,
    ADD COLUMN IF NOT EXISTS extraction_reasoning  TEXT,
    ADD COLUMN IF NOT EXISTS reviewed_by_human     BOOLEAN NOT NULL DEFAULT FALSE;
