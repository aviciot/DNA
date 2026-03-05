-- Migration 003: Link automation_config to llm_providers table
-- Adds extraction_provider_id FK; keeps flat columns as fallback

SET search_path TO dna_app;

ALTER TABLE dna_app.automation_config
    ADD COLUMN IF NOT EXISTS extraction_provider_id UUID
        REFERENCES dna_app.llm_providers(id) ON DELETE SET NULL;

-- Seed groq provider if not present
INSERT INTO dna_app.llm_providers (name, display_name, model, api_key_env, enabled)
VALUES ('groq', 'Groq', 'llama-3.1-8b-instant', 'GROQ_API_KEY', true)
ON CONFLICT (name) DO UPDATE SET
    model = EXCLUDED.model,
    enabled = true;

-- Point automation_config at groq
UPDATE dna_app.automation_config
SET extraction_provider_id = (SELECT id FROM dna_app.llm_providers WHERE name = 'groq'),
    extraction_provider = 'groq',
    extraction_model = 'llama-3.1-8b-instant'
WHERE id = 1;

SELECT 'Migration 003 complete' AS result;
