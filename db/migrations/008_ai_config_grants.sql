-- Migration 008: Grant portal_user access to ai_config (replaces ai_settings)
-- ai_settings was dropped and consolidated into ai_config

GRANT SELECT ON dna_app.ai_config TO portal_user;
