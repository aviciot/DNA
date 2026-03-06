-- ============================================================
-- Migration 005: Customer Portal MCP
-- Seeds system prompt, chat config defaults, and DB grants
-- ============================================================

-- System prompt (loaded by portal_assistant prompt at runtime)
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, model, max_tokens, description, is_active)
VALUES (
  'portal_mcp_system',
  'You are a friendly ISO compliance assistant for {customer_name}, helping them complete their {iso_name} certification.

RULES:
- Always respond in {language}
- Only discuss tasks, documents, and questions related to this customer''s compliance plan
- Never invent information — only use data returned by tools
- Never discuss other customers, internal systems, or unrelated topics
- Current status: {pending_count} tasks pending out of total
- Be encouraging, explain WHY each question matters for {iso_code} compliance
- When explaining a task, reference the document it belongs to and the ISO clause it covers
- If asked off-topic, respond only in {language}: "I can only help with your {iso_name} compliance tasks"
- If you don''t have data for something, say so — never guess',
  'gemini-2.5-flash',
  8192,
  'Portal MCP chat system prompt — interpolated per customer session',
  true
) ON CONFLICT (prompt_key) DO NOTHING;

-- Global MCP chat config defaults (customer_id = NULL = global fallback)
INSERT INTO dna_app.customer_configuration
  (customer_id, config_type, config_key, config_value, is_default, is_active)
VALUES
  (NULL, 'mcp_chat', 'language',             '"en"',       true, true),
  (NULL, 'mcp_chat', 'chat_tone',            '"friendly"', true, true),
  (NULL, 'mcp_chat', 'max_context_messages', '20',         true, true),
  (NULL, 'mcp_chat', 'max_tokens',           '8192',       true, true)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;

-- Grants for portal_user (read-only on new tables, insert on usage log)
GRANT SELECT ON dna_app.ai_prompts            TO portal_user;
GRANT SELECT ON dna_app.customer_configuration TO portal_user;
GRANT SELECT ON dna_app.templates             TO portal_user;
GRANT SELECT ON dna_app.customer_documents    TO portal_user;
GRANT SELECT ON dna_app.llm_providers         TO portal_user;
GRANT INSERT ON dna_app.ai_usage_log          TO portal_user;
