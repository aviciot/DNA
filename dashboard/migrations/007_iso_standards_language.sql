ALTER TABLE dna_app.iso_standards ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'en';
UPDATE dna_app.iso_standards SET language = 'en' WHERE language IS NULL;
ALTER TABLE dna_app.iso_standards DROP CONSTRAINT IF EXISTS iso_standards_code_key;
ALTER TABLE dna_app.iso_standards ADD CONSTRAINT iso_standards_code_language_key UNIQUE (code, language);
