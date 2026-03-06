-- Migration 016: Consolidate AI provider configuration into global_ai_config
-- Replaces: ai_settings (key-value anti-pattern) + extraction_* columns in automation_config
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Create new unified config table
CREATE TABLE IF NOT EXISTS dna_app.global_ai_config (
    id                   INTEGER PRIMARY KEY DEFAULT 1,
    iso_builder_provider VARCHAR(50)  NOT NULL DEFAULT 'gemini',
    iso_builder_model    VARCHAR(100),          -- NULL = use llm_providers.model
    extraction_provider  VARCHAR(50)  NOT NULL DEFAULT 'gemini',
    extraction_model     VARCHAR(100),          -- NULL = use llm_providers.model
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Seed with current values (migrate existing data)
INSERT INTO dna_app.global_ai_config (id, iso_builder_provider, iso_builder_model, extraction_provider, extraction_model)
SELECT
    1,
    COALESCE(
        (SELECT value FROM dna_app.ai_settings WHERE key = 'active_provider'),
        'gemini'
    ),
    NULLIF(
        (SELECT value FROM dna_app.ai_settings WHERE key = 'active_model'),
        ''
    ),
    COALESCE(
        (SELECT extraction_provider FROM dna_app.automation_config WHERE id = 1),
        'gemini'
    ),
    NULLIF(
        (SELECT extraction_model FROM dna_app.automation_config WHERE id = 1),
        ''
    )
ON CONFLICT (id) DO NOTHING;

-- 3. Drop ai_settings (replaced by global_ai_config)
DROP TABLE IF EXISTS dna_app.ai_settings;

-- 4. Drop extraction_* columns from automation_config (now in global_ai_config)
ALTER TABLE dna_app.automation_config
    DROP COLUMN IF EXISTS extraction_provider,
    DROP COLUMN IF EXISTS extraction_model;
