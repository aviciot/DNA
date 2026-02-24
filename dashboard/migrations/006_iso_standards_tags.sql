-- Migration 006: Add tags to iso_standards
ALTER TABLE dna_app.iso_standards ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT ARRAY[]::TEXT[];
CREATE INDEX IF NOT EXISTS idx_iso_standards_tags ON dna_app.iso_standards USING gin(tags);
