-- Migration 006: Portal Config Defaults
-- Seeds ai_settings for portal_chat provider/model
-- Seeds portal_settings global defaults in customer_configuration

-- LLM provider for portal chat (picks up existing default chat provider)
INSERT INTO dna_app.ai_settings (key, value)
SELECT 'portal_chat_provider', value FROM dna_app.ai_settings WHERE key = 'iso_builder_provider'
ON CONFLICT (key) DO NOTHING;

INSERT INTO dna_app.ai_settings (key, value)
SELECT 'portal_chat_model', value FROM dna_app.ai_settings WHERE key = 'iso_builder_model'
ON CONFLICT (key) DO NOTHING;

-- Fallback if iso_builder_provider doesn't exist
INSERT INTO dna_app.ai_settings (key, value) VALUES ('portal_chat_provider', 'gemini')
ON CONFLICT (key) DO NOTHING;

INSERT INTO dna_app.ai_settings (key, value) VALUES ('portal_chat_model', 'gemini-1.5-pro')
ON CONFLICT (key) DO NOTHING;

-- portal_settings global defaults
INSERT INTO dna_app.customer_configuration
    (customer_id, config_type, config_key, config_value, is_default, is_active)
VALUES
    (NULL, 'portal_settings', 'token_expiry_days', '30',   true, true),
    (NULL, 'portal_settings', 'require_av_scan',   'true', true, true),
    (NULL, 'portal_settings', 'max_upload_mb',     '10',   true, true)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;
