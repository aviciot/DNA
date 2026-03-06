-- Migration 017: Simplified AI configuration
-- - llm_providers: drop 'model' column, add 'available_models' JSONB
-- - Create 'ai_config' table: one row per service (iso_builder, extraction)
-- - Drop global_ai_config
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Add available_models to llm_providers
ALTER TABLE dna_app.llm_providers
    ADD COLUMN IF NOT EXISTS available_models JSONB NOT NULL DEFAULT '[]';

-- 2. Seed available_models
UPDATE dna_app.llm_providers
SET available_models = '["gemini-2.5-flash","gemini-2.5-pro","gemini-2.0-flash","gemini-1.5-pro"]'::jsonb
WHERE name = 'gemini';

UPDATE dna_app.llm_providers
SET available_models = '["claude-sonnet-4-6","claude-sonnet-4-5-20250929","claude-haiku-4-5-20251001","claude-opus-4-6"]'::jsonb
WHERE name = 'claude';

UPDATE dna_app.llm_providers
SET available_models = '["llama-3.3-70b-versatile","llama-3.1-8b-instant","moonshotai/kimi-k2-instruct"]'::jsonb
WHERE name = 'groq';

UPDATE dna_app.llm_providers
SET available_models = '["gpt-4o","gpt-4-turbo","gpt-4o-mini"]'::jsonb
WHERE name = 'openai';

-- 3. Drop old model column from llm_providers
ALTER TABLE dna_app.llm_providers
    DROP COLUMN IF EXISTS model;

-- 4. Create ai_config table (one row per service)
CREATE TABLE IF NOT EXISTS dna_app.ai_config (
    service    VARCHAR(50)  PRIMARY KEY,   -- 'iso_builder' | 'extraction'
    provider   VARCHAR(50)  NOT NULL,      -- must match llm_providers.name
    model      VARCHAR(100) NOT NULL,
    updated_at TIMESTAMPTZ  DEFAULT NOW()
);

-- 5. Migrate data from global_ai_config (if it still exists from migration 016)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'dna_app' AND table_name = 'global_ai_config'
    ) THEN
        INSERT INTO dna_app.ai_config (service, provider, model)
        SELECT
            'iso_builder',
            COALESCE(NULLIF(iso_builder_provider, ''), 'gemini'),
            COALESCE(NULLIF(iso_builder_model, ''), 'gemini-2.5-pro')
        FROM dna_app.global_ai_config WHERE id = 1
        ON CONFLICT DO NOTHING;

        INSERT INTO dna_app.ai_config (service, provider, model)
        SELECT
            'extraction',
            COALESCE(NULLIF(extraction_provider, ''), 'gemini'),
            COALESCE(NULLIF(extraction_model, ''), 'gemini-2.5-flash')
        FROM dna_app.global_ai_config WHERE id = 1
        ON CONFLICT DO NOTHING;
    END IF;
END;
$$;

-- 6. Defaults if global_ai_config was missing
INSERT INTO dna_app.ai_config (service, provider, model)
VALUES ('iso_builder', 'gemini', 'gemini-2.5-pro')
ON CONFLICT DO NOTHING;

INSERT INTO dna_app.ai_config (service, provider, model)
VALUES ('extraction', 'gemini', 'gemini-2.5-flash')
ON CONFLICT DO NOTHING;

-- 7. Drop global_ai_config
DROP TABLE IF EXISTS dna_app.global_ai_config;
