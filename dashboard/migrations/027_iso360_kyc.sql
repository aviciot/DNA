-- Migration 027: ISO360 KYC Questionnaire
-- Creates iso360_kyc_batches table and adds kyc_batch_id to customer_tasks

-- KYC batch tracker (one per customer × plan × trigger)
CREATE TABLE IF NOT EXISTS dna_app.iso360_kyc_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     INT  NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id         UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    status          VARCHAR(30) NOT NULL DEFAULT 'generating',
    -- statuses: generating → pending → completed → adjustment_triggered → failed
    total_questions INT  NOT NULL DEFAULT 0,
    answered_count  INT  NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_kyc_batches_customer_plan
    ON dna_app.iso360_kyc_batches (customer_id, plan_id);

-- Link tasks back to the batch that created them
ALTER TABLE dna_app.customer_tasks
    ADD COLUMN IF NOT EXISTS kyc_batch_id UUID REFERENCES dna_app.iso360_kyc_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_customer_tasks_kyc_batch
    ON dna_app.customer_tasks (kyc_batch_id) WHERE kyc_batch_id IS NOT NULL;

-- AI prompts for KYC question generation
-- iso360_kyc_system: stored as system prompt in prompt_text
-- iso360_kyc_user: stored as user template in prompt_text
INSERT INTO dna_app.ai_prompts (prompt_key, prompt_text, description)
VALUES (
    'iso360_kyc_system',
    'You are a compliance consultant specialising in ISO management systems. Your role is to generate targeted onboarding questions that help personalise an ISO compliance plan for a specific customer. Questions should be practical, specific, and answerable by a non-technical business owner or manager. Each question should help tailor compliance activities to their real environment.',
    'ISO360 KYC: system prompt for generating onboarding questionnaire'
),
(
    'iso360_kyc_user',
    E'You are onboarding a new customer onto an ISO {{iso_code}} compliance programme.\n\nCustomer profile:\n- Company name: {{customer_name}}\n- Industry: {{industry}}\n- Size: {{company_size}}\n\nGenerate exactly 10 practical onboarding questions that will help personalise the ISO {{iso_code}} compliance activities for this customer. Focus on:\n- Their existing processes and tools relevant to {{iso_code}}\n- Their team structure and who owns compliance\n- Their current documentation practices\n- Key risks or gaps specific to their industry and size\n- Any certifications or frameworks they already have in place\n\nReturn ONLY valid JSON — an array of 10 objects, each with:\n{\n  "key": "unique_snake_case_key",\n  "question": "The full question text",\n  "category": "one of: team | processes | tools | documentation | risk",\n  "hint": "optional short hint for the user answering this"\n}\n\nNo preamble, no explanation, only the JSON array.',
    'ISO360 KYC: user prompt template for generating onboarding questionnaire'
)
ON CONFLICT (prompt_key) DO UPDATE
    SET prompt_text = EXCLUDED.prompt_text,
        description = EXCLUDED.description,
        updated_at  = NOW();
