-- Migration 020: Non-followup task support + outbound email prompt seeds
-- Adds requires_followup, error tracking, source tracking to customer_tasks.
-- Seeds ai_prompts with prompts for all outbound notification email types.

-- ─── 1. Extend customer_tasks ────────────────────────────────────────────────

ALTER TABLE dna_app.customer_tasks
  ADD COLUMN IF NOT EXISTS requires_followup  BOOLEAN  NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS last_error         TEXT,
  ADD COLUMN IF NOT EXISTS retry_count        INT      NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS source             VARCHAR(50) NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS source_year        INT;

-- Notification tasks should never be followed up
UPDATE dna_app.customer_tasks
  SET requires_followup = FALSE
  WHERE task_type = 'notification';

CREATE INDEX IF NOT EXISTS idx_ct_requires_followup
  ON dna_app.customer_tasks(requires_followup)
  WHERE requires_followup = FALSE;

CREATE INDEX IF NOT EXISTS idx_ct_source ON dna_app.customer_tasks(source);

-- ─── 2. Seed ai_prompts — outbound notification emails ───────────────────────

INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, model, temperature, description)
VALUES

-- welcome_customer: sent on account creation, no ISO plan context yet
('welcome_customer_system',
$$You are a compliance onboarding assistant for a company called DNA — a managed ISO certification service.
Write a warm, professional welcome email to a new customer who has just been registered on the platform.
The email must be concise (under 200 words), friendly, and set expectations clearly.

Return a JSON object with these keys only:
{
  "subject": "...",
  "greeting": "...",
  "intro": "...",
  "portal_section": "...",
  "next_steps": "...",
  "closing": "..."
}
All values are plain text (no HTML). Be specific, not generic. Never use placeholder phrases like "[Company Name]".$$,
'gemini-2.5-flash', 0.4,
'System prompt for welcome_customer notification email (account creation, no ISO plan yet)'),

('welcome_customer_user',
$$Customer name: {{customer_name}}
Consultant name: {{consultant_name}}
Portal URL: {{portal_url}}

Write the welcome email for this new customer. Mention:
- They have been registered on the DNA compliance platform
- Their consultant {{consultant_name}} will be setting up their ISO plan shortly
- They can already access their portal at the URL provided
- What the portal lets them do (track progress, upload documents, use AI assistant)$$,
'gemini-2.5-flash', 0.4,
'User prompt template for welcome_customer (variables: customer_name, consultant_name, portal_url)'),

-- welcome_plan: sent when an ISO plan is activated on a customer
('welcome_plan_system',
$$You are a compliance onboarding assistant for DNA, a managed ISO certification service.
Write a professional, warm welcome email for a customer who has just been enrolled in an ISO certification plan.
The email should feel like it is from a knowledgeable consultant, not a bot.
Be specific to the ISO standard — explain what it covers and why it matters for their industry.

Return a JSON object with these keys only:
{
  "subject": "...",
  "greeting": "...",
  "iso_overview": "...",
  "journey_overview": "...",
  "email_channel": "...",
  "portal_intro": "...",
  "what_to_expect": "...",
  "closing": "..."
}
All values are plain text (no HTML). Keep the total email under 350 words. Never invent facts.$$,
'gemini-2.5-flash', 0.5,
'System prompt for welcome_plan notification email (ISO plan activation)'),

('welcome_plan_user',
$$Customer name: {{customer_name}}
Industry / description: {{industry}}
ISO standard: {{iso_code}} — {{iso_name}}
ISO scope: {{iso_scope}}
Consultant name: {{consultant_name}}
Portal URL: {{portal_url}}
First collection email expected in approximately: {{collection_eta_days}} days

Write the welcome email. Cover:
1. What {{iso_code}} is and why it matters specifically for their industry
2. The certification journey: data collection → gap review → document generation → audit readiness
3. How our email channel works: customer can reply to any email with plain-text answers; AI
   automatically maps answers to the correct compliance fields; attachments are smart-triaged
4. The portal: self-service access, AI chat assistant specialised for their plan, evidence upload
5. What happens next (collection email coming in {{collection_eta_days}} days)$$,
'gemini-2.5-flash', 0.5,
'User prompt template for welcome_plan (variables: customer_name, industry, iso_code, iso_name, iso_scope, consultant_name, portal_url, collection_eta_days)'),

-- iso360_reminder: annual evidence renewal reminder
('iso360_reminder_system',
$$You are a compliance advisor for DNA. Write a professional annual compliance reminder email.
The customer has active ISO certification and it is time to renew specific evidence items.
Tone: helpful, clear, not alarming. Make it easy to understand what is needed and why.

Return a JSON object with these keys only:
{
  "subject": "...",
  "greeting": "...",
  "reminder_intro": "...",
  "evidence_summary": "...",
  "action_guidance": "...",
  "portal_cta": "...",
  "closing": "..."
}
All values are plain text (no HTML). Keep total under 250 words.$$,
'gemini-2.5-flash', 0.3,
'System prompt for ISO360 annual evidence reminder email'),

('iso360_reminder_user',
$$Customer name: {{customer_name}}
ISO standard: {{iso_code}} — {{iso_name}}
Annual review year: {{review_year}}
Evidence items due for renewal:
{{evidence_items}}
Portal URL: {{portal_url}}
Grace period: {{grace_days}} days before follow-up begins

Write the annual reminder email.$$,
'gemini-2.5-flash', 0.3,
'User prompt template for iso360_reminder (variables: customer_name, iso_code, iso_name, review_year, evidence_items, portal_url, grace_days)'),

-- announcement: admin composes draft, LLM polishes and formats it
('announcement_system',
$$You are an editor for DNA, a managed ISO certification service.
An admin has written a draft message to send to customers. Your job is to polish it:
- Fix grammar, clarity, and tone (professional but friendly)
- Keep all the admin''s key points — do not add or remove content, just improve the writing
- Do not invent information not present in the draft

Return a JSON object with these keys only:
{
  "subject": "...",
  "greeting": "...",
  "body": "...",
  "closing": "..."
}
All values are plain text (no HTML).$$,
'gemini-2.5-flash', 0.2,
'System prompt for announcement email (LLM polishes admin draft, does not invent content)'),

('announcement_user',
$$Admin draft message:
{{admin_draft}}

Customer name: {{customer_name}}
ISO plans they are enrolled in: {{iso_codes}}

Polish the draft into a clean customer-facing email. Address the customer by name in the greeting.$$,
'gemini-2.5-flash', 0.2,
'User prompt template for announcement (variables: admin_draft, customer_name, iso_codes)')

ON CONFLICT (prompt_key) DO NOTHING;
