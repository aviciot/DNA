-- Migration 003: Store encrypted API keys in llm_providers
-- Each service reads the key from this table instead of env vars

SET search_path TO dna_app;

ALTER TABLE dna_app.llm_providers
    ADD COLUMN IF NOT EXISTS api_key TEXT;  -- stored as 'enc:<fernet_token>'

-- Seed/update groq
INSERT INTO dna_app.llm_providers (name, display_name, model, api_key_env, enabled)
VALUES ('groq', 'Groq', 'llama-3.1-8b-instant', 'GROQ_API_KEY', true)
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    model        = EXCLUDED.model,
    enabled      = true;

SELECT 'Migration 003 complete' AS result;
