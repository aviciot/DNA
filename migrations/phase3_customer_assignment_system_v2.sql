-- =====================================================
-- Phase 3: Customer Assignment System - Migration V2
-- Date: 2026-02-13
-- Description: Core schema for customer management,
--              task system, and configuration
--              UPDATED: Works with existing schema
-- =====================================================

BEGIN;

-- =====================================================
-- 1. CREATE: customer_configuration TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS dna_app.customer_configuration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    -- NULL customer_id means global default configuration

    -- Configuration Type
    config_type VARCHAR(100) NOT NULL,
        -- 'welcome_email', 'assignment_notification', 'reminder_email',
        -- 'evidence_request', 'approval_notification', 'rejection_notification',
        -- 'branding', 'communication_preferences', 'workflow_settings'

    -- Configuration Content
    config_key VARCHAR(255) NOT NULL,
    config_value JSONB NOT NULL,
        -- For emails: {subject, body, from_name, cc, bcc}
        -- For branding: {logo_url, primary_color, secondary_color, font}
        -- For preferences: {notification_channels, frequency, language}

    -- Template/Format
    is_template BOOLEAN DEFAULT false,
    template_variables JSONB,
        -- e.g., [{"name": "company_name", "type": "string"}, {"name": "due_date", "type": "date"}]

    -- AI Enhancement (Future)
    use_ai_phrasing BOOLEAN DEFAULT false,
    ai_tone VARCHAR(50),
    ai_last_generated_at TIMESTAMP,
    ai_generation_prompt TEXT,

    -- Status
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES auth.users(id),
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by INTEGER REFERENCES auth.users(id),

    -- Constraints
    UNIQUE(customer_id, config_type, config_key)
);

CREATE INDEX IF NOT EXISTS idx_customer_config_customer ON dna_app.customer_configuration(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_config_type ON dna_app.customer_configuration(config_type);
CREATE INDEX IF NOT EXISTS idx_customer_config_active ON dna_app.customer_configuration(is_active);

COMMENT ON TABLE dna_app.customer_configuration IS 'Flexible configuration store for customer-specific settings, templates, and preferences';
COMMENT ON COLUMN dna_app.customer_configuration.customer_id IS 'NULL = global default configuration, INTEGER = customer-specific';
COMMENT ON COLUMN dna_app.customer_configuration.template_variables IS 'JSON array defining available variables for template interpolation';
COMMENT ON COLUMN dna_app.customer_configuration.use_ai_phrasing IS 'Enable AI-powered content generation for this configuration';

-- =====================================================
-- 2. ALTER: customer_tasks TABLE (Add Manual Tasks & Ignored Status)
-- =====================================================

-- Add new columns to customer_tasks table (if not exists)
DO $$
BEGIN
    -- is_ignored column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'is_ignored') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN is_ignored BOOLEAN DEFAULT false;
    END IF;

    -- ignored_at column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'ignored_at') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN ignored_at TIMESTAMP;
    END IF;

    -- ignored_by column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'ignored_by') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN ignored_by INTEGER REFERENCES auth.users(id);
    END IF;

    -- ignore_reason column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'ignore_reason') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN ignore_reason TEXT;
    END IF;

    -- created_manually_by column (different from created_by)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'created_manually_by') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN created_manually_by INTEGER REFERENCES auth.users(id);
    END IF;

    -- manual_task_context column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_tasks'
                   AND column_name = 'manual_task_context') THEN
        ALTER TABLE dna_app.customer_tasks ADD COLUMN manual_task_context TEXT;
    END IF;

    -- Update auto_generated column default (column already exists)
    -- auto_generated already exists from customer_tasks table creation
END $$;

COMMENT ON COLUMN dna_app.customer_tasks.auto_generated IS 'true = system generated from questions, false = manually created by admin';
COMMENT ON COLUMN dna_app.customer_tasks.is_ignored IS 'true = task marked as irrelevant/ignored (e.g. template removed)';
COMMENT ON COLUMN dna_app.customer_tasks.created_manually_by IS 'User who manually created this task (NULL if auto-generated)';
COMMENT ON COLUMN dna_app.customer_tasks.manual_task_context IS 'Additional context for manual tasks';

-- =====================================================
-- 3. ALTER: customer_iso_plans TABLE (Add Ignored Status)
-- =====================================================

DO $$
BEGIN
    -- is_ignored column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_iso_plans'
                   AND column_name = 'is_ignored') THEN
        ALTER TABLE dna_app.customer_iso_plans ADD COLUMN is_ignored BOOLEAN DEFAULT false;
    END IF;

    -- ignored_at column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_iso_plans'
                   AND column_name = 'ignored_at') THEN
        ALTER TABLE dna_app.customer_iso_plans ADD COLUMN ignored_at TIMESTAMP;
    END IF;

    -- ignored_by column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_iso_plans'
                   AND column_name = 'ignored_by') THEN
        ALTER TABLE dna_app.customer_iso_plans ADD COLUMN ignored_by INTEGER REFERENCES auth.users(id);
    END IF;

    -- ignore_reason column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'dna_app'
                   AND table_name = 'customer_iso_plans'
                   AND column_name = 'ignore_reason') THEN
        ALTER TABLE dna_app.customer_iso_plans ADD COLUMN ignore_reason TEXT;
    END IF;
END $$;

COMMENT ON COLUMN dna_app.customer_iso_plans.is_ignored IS 'true = plan marked as irrelevant (but kept for history)';

-- =====================================================
-- 4. CREATE: task_resolutions TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS dna_app.task_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    task_id UUID NOT NULL REFERENCES dna_app.customer_tasks(id) ON DELETE CASCADE,

    -- Resolution Details
    resolution_type VARCHAR(50) NOT NULL,
        -- 'answer_provided', 'evidence_uploaded', 'approved', 'rejected',
        -- 'delegated', 'merged', 'split', 'clarification_requested', 'manual_completion'

    resolution_data JSONB,
        -- For answers: {"answer": "...", "question_placeholder": "..."}
        -- For evidence: {"file_path": "...", "file_name": "...", "file_size": 123456}
        -- For delegation: {"delegated_to": user_id, "reason": "..."}
        -- For manual: {"completion_notes": "...", "metadata": {...}}

    -- Resolution Status
    is_final BOOLEAN DEFAULT false,
    requires_approval BOOLEAN DEFAULT false,
    approved_at TIMESTAMP,
    approved_by INTEGER REFERENCES auth.users(id),

    -- Quality
    quality_score INTEGER CHECK (quality_score >= 1 AND quality_score <= 5),
    completeness_score INTEGER CHECK (completeness_score >= 0 AND completeness_score <= 100),

    -- User Tracking
    resolved_by INTEGER REFERENCES auth.users(id),
    resolved_at TIMESTAMP DEFAULT NOW(),

    -- Follow-up
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_task_id UUID REFERENCES dna_app.customer_tasks(id),

    -- Metadata
    notes TEXT,
    attachments JSONB
);

CREATE INDEX IF NOT EXISTS idx_task_resolution_task ON dna_app.task_resolutions(task_id);
CREATE INDEX IF NOT EXISTS idx_task_resolution_type ON dna_app.task_resolutions(resolution_type);
CREATE INDEX IF NOT EXISTS idx_task_resolution_requires_approval ON dna_app.task_resolutions(requires_approval) WHERE requires_approval = true;

COMMENT ON TABLE dna_app.task_resolutions IS 'Track how tasks are resolved, including answers, evidence, approvals, etc.';

-- =====================================================
-- 5. CREATE: task_templates TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS dna_app.task_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Template Details
    template_name VARCHAR(255) NOT NULL,
    template_description TEXT,

    task_type VARCHAR(100) NOT NULL,
    task_scope VARCHAR(50) NOT NULL, -- customer, plan, document, question

    -- Default Values
    default_title VARCHAR(500),
    default_description TEXT,
    default_priority VARCHAR(50) DEFAULT 'medium',
    default_due_in_days INTEGER,

    -- Checklist (for complex tasks)
    checklist_items JSONB,
        -- [{"title": "Review document", "completed": false}, ...]

    -- Status
    is_active BOOLEAN DEFAULT true,
    is_system_template BOOLEAN DEFAULT false,

    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES auth.users(id)
);

CREATE INDEX IF NOT EXISTS idx_task_template_type ON dna_app.task_templates(task_type);
CREATE INDEX IF NOT EXISTS idx_task_template_active ON dna_app.task_templates(is_active);
CREATE INDEX IF NOT EXISTS idx_task_template_scope ON dna_app.task_templates(task_scope);

COMMENT ON TABLE dna_app.task_templates IS 'Reusable templates for creating manual tasks quickly';

-- =====================================================
-- 6. INSERT: "stand_alone" ISO Standard
-- =====================================================

-- First, we need to temporarily drop and recreate the code_format constraint
-- to allow "stand_alone" as a valid code
ALTER TABLE dna_app.iso_standards DROP CONSTRAINT IF EXISTS code_format;

-- Add updated constraint that allows either ISO format or "stand_alone"
ALTER TABLE dna_app.iso_standards
ADD CONSTRAINT code_format CHECK (
    code ~ '^ISO [0-9]+:[0-9]{4}$' OR code = 'stand_alone'
);

-- Now insert the stand_alone ISO standard
INSERT INTO dna_app.iso_standards (
    id,
    code,
    name,
    description,
    active,
    created_at
) VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    'stand_alone',
    'Stand-alone Templates',
    'Templates not associated with any specific ISO standard',
    true,
    NOW()
)
ON CONFLICT (id) DO NOTHING;

COMMENT ON COLUMN dna_app.iso_standards.code IS 'ISO standard code (format: "ISO XXXXX:YYYY" or "stand_alone" for non-ISO templates)';

-- =====================================================
-- 7. CREATE: v_customer_iso_progress VIEW
-- =====================================================

-- Drop existing view if it exists (can't use OR REPLACE with incompatible changes)
DROP VIEW IF EXISTS dna_app.v_customer_iso_progress CASCADE;

CREATE VIEW dna_app.v_customer_iso_progress AS
SELECT
    cip.id,
    cip.customer_id,
    cip.iso_standard_id,
    iso.code as iso_code,
    iso.name as iso_name,

    -- Plan details
    cip.plan_name,
    cip.plan_status,
    cip.target_completion_date,

    -- Template counts
    COUNT(DISTINCT ipt.template_id) as total_templates,
    COUNT(DISTINCT CASE WHEN cd.status = 'completed' THEN cd.template_id END) as completed_templates,
    COUNT(DISTINCT CASE WHEN cd.status IN ('in_progress', 'draft') THEN cd.template_id END) as in_progress_templates,

    -- Task counts (excluding ignored)
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false) as total_tasks,
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND ct.is_ignored = false) as completed_tasks,
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'in_progress' AND ct.is_ignored = false) as in_progress_tasks,
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'pending' AND ct.is_ignored = false) as pending_tasks,
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = true) as ignored_tasks,

    -- Progress percentage (excluding ignored tasks)
    CASE
        WHEN COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false) = 0 THEN 0
        ELSE (COUNT(DISTINCT ct.id) FILTER (WHERE ct.status = 'completed' AND ct.is_ignored = false)::float /
              COUNT(DISTINCT ct.id) FILTER (WHERE ct.is_ignored = false)::float * 100)::integer
    END as progress_percentage,

    -- Timestamps
    cip.created_at,
    cip.updated_at

FROM dna_app.customer_iso_plans cip
LEFT JOIN dna_app.iso_standards iso ON cip.iso_standard_id = iso.id
LEFT JOIN dna_app.customer_iso_plan_templates ipt ON cip.id = ipt.plan_id
LEFT JOIN dna_app.customer_documents cd
    ON cip.id = cd.plan_id
    AND cip.customer_id = cd.customer_id
LEFT JOIN dna_app.customer_tasks ct
    ON cip.id = ct.plan_id
WHERE cip.is_ignored = false OR cip.is_ignored IS NULL
GROUP BY cip.id, cip.customer_id, cip.iso_standard_id, iso.code, iso.name,
         cip.plan_name, cip.plan_status, cip.target_completion_date,
         cip.created_at, cip.updated_at;

COMMENT ON VIEW dna_app.v_customer_iso_progress IS 'Customer progress tracking per ISO standard (excluding ignored tasks)';

-- =====================================================
-- 8. INSERT: Default Configuration Templates
-- =====================================================

-- Default Welcome Email Template
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    is_default,
    template_variables,
    is_active,
    created_at
) VALUES (
    NULL, -- Global default
    'welcome_email',
    'default_welcome',
    '{
        "subject": "Welcome to DNA Compliance Platform, {{company_name}}!",
        "body": "Dear {{primary_contact}},\n\nWelcome to the DNA Compliance Platform! We are excited to partner with {{company_name}} on your compliance journey.\n\nYou have been assigned {{template_count}} compliance templates to complete. Your personalized dashboard is ready at:\n\n{{dashboard_url}}\n\nLogin Credentials:\nEmail: {{customer_email}}\nTemporary Password: {{temp_password}}\n\n(Please change your password after first login)\n\nNext Steps:\n1. Log in to your dashboard\n2. Review your assigned templates\n3. Complete the compliance questionnaires\n4. Upload any required evidence\n\nOur team is here to help! If you have any questions, reply to this email or contact your account manager.\n\nBest regards,\nThe DNA Compliance Team",
        "from_name": "DNA Compliance Support",
        "from_email": "support@dna-compliance.com",
        "reply_to": "support@dna-compliance.com"
    }',
    true,
    true,
    '[
        {"name": "company_name", "type": "string", "description": "Customer company name"},
        {"name": "primary_contact", "type": "string", "description": "Primary contact name"},
        {"name": "customer_email", "type": "string", "description": "Customer login email"},
        {"name": "template_count", "type": "number", "description": "Number of assigned templates"},
        {"name": "dashboard_url", "type": "string", "description": "Link to customer dashboard"},
        {"name": "temp_password", "type": "string", "description": "Temporary password"}
    ]'::JSONB,
    true,
    NOW()
)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;

-- Default Evidence Request Template
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    is_default,
    template_variables,
    is_active,
    created_at
) VALUES (
    NULL,
    'evidence_request',
    'default_evidence_request',
    '{
        "subject": "Evidence Required: {{template_name}}",
        "body": "Dear {{company_name}},\n\nFor the {{template_name}} template, we require evidence for the following:\n\nQuestion: {{question_title}}\n\nEvidence Needed: {{evidence_description}}\n\nPlease upload your evidence document(s) in your dashboard:\n{{evidence_upload_url}}\n\nAccepted formats: PDF, Word, Excel, Images\nMax file size: 10MB\n\nDue Date: {{due_date}}\n\nIf you have any questions about what evidence is required, please contact us.\n\nThank you,\nThe DNA Compliance Team",
        "from_name": "DNA Compliance Support",
        "reminder_days": [7, 3, 1]
    }',
    true,
    true,
    '[
        {"name": "company_name", "type": "string", "description": "Customer company name"},
        {"name": "template_name", "type": "string", "description": "Template name requiring evidence"},
        {"name": "question_title", "type": "string", "description": "The specific question/placeholder"},
        {"name": "evidence_description", "type": "string", "description": "Description of required evidence"},
        {"name": "evidence_upload_url", "type": "string", "description": "Direct link to upload evidence"},
        {"name": "due_date", "type": "date", "description": "Evidence submission due date"}
    ]'::JSONB,
    true,
    NOW()
)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;

-- Default Assignment Notification Template
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    is_default,
    template_variables,
    is_active,
    created_at
) VALUES (
    NULL,
    'assignment_notification',
    'default_assignment_notification',
    '{
        "subject": "New Template Assigned: {{template_name}}",
        "body": "Dear {{company_name}},\n\nA new compliance template has been assigned to you:\n\nTemplate: {{template_name}}\nDescription: {{template_description}}\nPriority: {{priority}}\nDue Date: {{due_date}}\n\nTotal Questions: {{question_count}}\nEstimated Time: {{estimated_time}}\n\nGet started here:\n{{template_url}}\n\nBest regards,\nThe DNA Compliance Team",
        "from_name": "DNA Compliance Support"
    }',
    true,
    true,
    '[
        {"name": "company_name", "type": "string", "description": "Customer company name"},
        {"name": "template_name", "type": "string", "description": "Assigned template name"},
        {"name": "template_description", "type": "string", "description": "Template description"},
        {"name": "priority", "type": "string", "description": "Assignment priority"},
        {"name": "due_date", "type": "date", "description": "Assignment due date"},
        {"name": "question_count", "type": "number", "description": "Number of questions"},
        {"name": "estimated_time", "type": "string", "description": "Estimated completion time"},
        {"name": "template_url", "type": "string", "description": "Direct link to template"}
    ]'::JSONB,
    true,
    NOW()
)
ON CONFLICT (customer_id, config_type, config_key) DO NOTHING;

-- =====================================================
-- 9. INSERT: Default Task Templates
-- =====================================================

INSERT INTO dna_app.task_templates (
    template_name,
    template_description,
    task_type,
    task_scope,
    default_title,
    default_description,
    default_priority,
    default_due_in_days,
    is_system_template,
    is_active
) VALUES
(
    'Schedule Kickoff Meeting',
    'Initial kickoff meeting to discuss compliance requirements and project timeline',
    'schedule_meeting',
    'customer',
    'Schedule kickoff meeting with {{company_name}}',
    'Arrange an initial kickoff meeting to:\n- Introduce the platform\n- Review assigned templates\n- Discuss timeline and expectations\n- Answer any questions',
    'high',
    3,
    true,
    true
),
(
    'Review Evidence',
    'Review evidence uploaded by customer for compliance documentation',
    'review_evidence',
    'document',
    'Review uploaded evidence for {{question_title}}',
    'Review the evidence uploaded by the customer:\n- Verify completeness\n- Check quality and relevance\n- Approve or request revisions',
    'medium',
    2,
    true,
    true
),
(
    'Escalate Issue',
    'Escalate an issue or blocker with customer to management',
    'escalate',
    'customer',
    'Escalate issue with {{company_name}}',
    'Escalate the following issue:\n- Document the problem\n- Propose resolution\n- Assign to appropriate team member',
    'urgent',
    1,
    true,
    true
),
(
    'Request Additional Information',
    'Request additional information or clarification from customer',
    'request_info',
    'plan',
    'Request additional information for {{template_name}}',
    'Request clarification from the customer regarding:\n- Specific questions or answers\n- Missing information\n- Evidence quality issues',
    'medium',
    5,
    true,
    true
),
(
    'Conduct Training',
    'Provide platform training or guidance to customer',
    'training',
    'customer',
    'Conduct platform training for {{company_name}}',
    'Schedule and conduct training session:\n- Platform navigation\n- How to complete templates\n- Evidence upload process\n- Best practices',
    'medium',
    7,
    true,
    true
),
(
    'Follow-up Call',
    'Schedule follow-up call to check progress and address concerns',
    'follow_up',
    'customer',
    'Follow-up call with {{company_name}}',
    'Schedule follow-up call to:\n- Check on progress\n- Address any concerns\n- Provide assistance if needed\n- Update timeline if necessary',
    'medium',
    7,
    true,
    true
),
(
    'Final Review',
    'Perform final review before document approval',
    'final_review',
    'plan',
    'Final review of {{template_name}}',
    'Conduct final comprehensive review:\n- All questions answered\n- All evidence provided\n- Quality check\n- Prepare for approval',
    'high',
    2,
    true,
    true
)
ON CONFLICT DO NOTHING;

-- =====================================================
-- 10. GRANTS (Ensure proper permissions)
-- =====================================================

-- Grant permissions on new tables
GRANT SELECT, INSERT, UPDATE, DELETE ON dna_app.customer_configuration TO dna_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON dna_app.task_resolutions TO dna_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON dna_app.task_templates TO dna_user;

-- Grant permissions on view
GRANT SELECT ON dna_app.v_customer_iso_progress TO dna_user;

-- =====================================================
-- 11. UPDATE: Update trigger for customer_configuration
-- =====================================================

CREATE OR REPLACE FUNCTION dna_app.update_customer_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_customer_config_updated_at ON dna_app.customer_configuration;
CREATE TRIGGER trigger_update_customer_config_updated_at
    BEFORE UPDATE ON dna_app.customer_configuration
    FOR EACH ROW
    EXECUTE FUNCTION dna_app.update_customer_config_updated_at();

-- =====================================================
-- COMMIT
-- =====================================================

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify tables created
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'dna_app'
AND table_name IN (
    'customer_configuration',
    'task_resolutions',
    'task_templates'
)
ORDER BY table_name;

-- Verify columns added to customer_tasks
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'dna_app'
AND table_name = 'customer_tasks'
AND column_name IN (
    'is_ignored',
    'ignored_at',
    'ignored_by',
    'ignore_reason',
    'created_manually_by',
    'manual_task_context'
)
ORDER BY column_name;

-- Verify columns added to customer_iso_plans
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'dna_app'
AND table_name = 'customer_iso_plans'
AND column_name IN (
    'is_ignored',
    'ignored_at',
    'ignored_by',
    'ignore_reason'
)
ORDER BY column_name;

-- Verify stand_alone ISO inserted
SELECT id, code, name
FROM dna_app.iso_standards
WHERE code = 'stand_alone';

-- Verify view created
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'dna_app'
AND table_name = 'v_customer_iso_progress';

-- Verify default configurations inserted
SELECT config_type, config_key, is_default
FROM dna_app.customer_configuration
WHERE customer_id IS NULL
AND is_default = true
ORDER BY config_type;

-- Verify task templates inserted
SELECT template_name, task_type, task_scope
FROM dna_app.task_templates
WHERE is_system_template = true
ORDER BY template_name;

-- =====================================================
-- END OF MIGRATION
-- =====================================================
