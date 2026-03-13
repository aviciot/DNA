-- Migration 026: ISO360 Phase 4a — excluded flag + notification prompt
-- Adds excluded column to customer_documents (scheduler skips excluded activities)
-- Adds iso360_activity_due notification email prompt

ALTER TABLE dna_app.customer_documents
    ADD COLUMN IF NOT EXISTS excluded BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_customer_docs_iso360_due
    ON dna_app.customer_documents (customer_id, document_type, next_due_date)
    WHERE document_type = 'iso360_activity' AND excluded = FALSE;

-- Notification email prompt for ISO360 activity due reminders
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, is_active)
VALUES (
    'iso360_activity_due_system',
    'You are a professional compliance consultant writing on behalf of a compliance management platform called DNA. Write a concise, professional notification email to a customer informing them that a compliance activity is due soon. Be clear, helpful, and action-oriented. Output only a JSON object with keys: subject, intro, body, cta_label.',
    TRUE
),
(
    'iso360_activity_due_user',
    'Write a notification email for the following due compliance activity.

Customer name: {{customer_name}}
ISO Standard: {{iso_code}} — {{iso_name}}
Activity title: {{activity_title}}
Responsible role: {{responsible_role}}
Due date: {{due_date}}
Days until due: {{days_until_due}}
Portal URL: {{portal_url}}

The email should:
1. Clearly state which activity is due and when
2. Mention the responsible role
3. Direct them to the portal to see the steps and upload evidence
4. Be under 120 words in the body

Output JSON only:
{
  "subject": "...",
  "intro": "...",
  "body": "...",
  "cta_label": "View Activity"
}',
    TRUE
)
ON CONFLICT (prompt_key) DO UPDATE
    SET prompt_text = EXCLUDED.prompt_text,
        is_active   = TRUE;
