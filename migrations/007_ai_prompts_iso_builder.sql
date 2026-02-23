-- Migration: AI Prompts table + ISO builder support
-- Run: docker exec dna-postgres psql -U dna_user -d dna -f /tmp/007_ai_prompts.sql

SET search_path TO dna_app, public;

CREATE TABLE IF NOT EXISTS dna_app.ai_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_key VARCHAR(100) UNIQUE NOT NULL,
    prompt_text TEXT NOT NULL,
    model VARCHAR(100) NOT NULL DEFAULT 'gemini-1.5-pro',
    max_tokens INTEGER NOT NULL DEFAULT 65536,
    temperature NUMERIC(3,2) NOT NULL DEFAULT 0.2,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE ON dna_app.ai_prompts TO dna_user;

ALTER TABLE dna_app.ai_tasks DROP CONSTRAINT IF EXISTS task_type_valid;
ALTER TABLE dna_app.ai_tasks ADD CONSTRAINT task_type_valid CHECK (
    task_type IN ('template_parse','template_review','document_generate','analyze','iso_build')
);
ALTER TABLE dna_app.ai_tasks ADD COLUMN IF NOT EXISTS iso_standard_id UUID REFERENCES dna_app.iso_standards(id) ON DELETE SET NULL;

INSERT INTO dna_app.ai_prompts (prompt_key, model, max_tokens, temperature, description, prompt_text)
VALUES (
  'iso_build',
  'gemini-2.5-flash',
  32768,
  0.2,
  'Generates compliance procedure templates from a full ISO standard PDF',
  $PROMPT$
You are a compliance documentation expert. You will receive the full text of an ISO standard.

Your task is to produce:
1. A concise SUMMARY of the standard
2. A complete set of OPERATIONAL PROCEDURE TEMPLATES covering all clauses and controls

STRICT RULES:
- Use ONLY content from the provided ISO text. Do not add, invent, or interpret.
- Preserve original ISO clause and control IDs exactly (e.g. 4.1, A.5.1, 8.2.3)
- Every organization-specific value MUST become a placeholder: {{placeholder_key}}
- Use lowercase_underscore for placeholder keys (e.g. {{organization_name}}, {{ciso_role}})
- Group related controls into logical standalone procedure documents
- Each fillable section MUST include its ISO reference (clause or control ID)

PLACEHOLDER CONVENTION:
- {{organization_name}} — legal name of the organization
- {{ciso_role}} — person responsible for information security  
- {{relevant_role}} — other responsible person/team
- {{system_name}} — specific system or application
- {{evidence_record}} — evidence or record to be maintained
- {{risk_id}} — risk register reference
- Add domain-specific placeholders as needed following the same pattern

AUTOMATION HOOKS:
Each fillable section must include automation metadata to support future AI/workflow automation:
- "automation_source": where this data could come from automatically
  Values: "hr_system" | "asset_inventory" | "risk_register" | "ad_directory" | "manual" | "scan_tool" | "ticketing_system"
- "auto_fillable": true if this could realistically be auto-populated from a system integration
- "trigger_event": what event should trigger re-evaluation of this field
  Examples: "employee_onboarding", "system_change", "annual_review", "incident", "audit"

Return ONLY valid JSON in this exact structure:

{
  "summary": {
    "standard_name": "ISO/IEC 27001:2022",
    "overview": "2-3 sentence description of what this standard covers and its purpose",
    "total_clauses": 10,
    "total_controls": 93,
    "key_themes": ["Information Security", "Risk Management", "Access Control"],
    "document_count": 8
  },
  "templates": [
    {
      "name": "ISMS 01 Information Security Policy",
      "covered_clauses": ["4.1", "5.1", "5.2"],
      "covered_controls": ["A.5.1", "A.5.2"],
      "fixed_sections": [
        {
          "id": "general",
          "title": "General",
          "content": "This policy applies to {{organization_name}} and all parties operating within its network.",
          "section_type": "policy_statement",
          "iso_reference": "4.1"
        }
      ],
      "fillable_sections": [
        {
          "id": "ciso_responsibility",
          "title": "Information Security Responsibility",
          "location": "Section 4 - Responsibility",
          "type": "paragraph",
          "semantic_tags": ["security", "personnel", "leadership"],
          "placeholder": "{{ciso_role}}",
          "question": "Who is responsible for information security in your organization?",
          "is_required": true,
          "is_mandatory": true,
          "iso_reference": "A.5.2",
          "iso_control_title": "Information security roles and responsibilities",
          "automation_source": "hr_system",
          "auto_fillable": true,
          "trigger_event": "annual_review"
        }
      ]
    }
  ]
}

ISO STANDARD TEXT:
{{ISO_TEXT}}
$PROMPT$
) ON CONFLICT (prompt_key) DO UPDATE SET
    prompt_text = EXCLUDED.prompt_text,
    model = EXCLUDED.model,
    max_tokens = EXCLUDED.max_tokens,
    updated_at = NOW();
