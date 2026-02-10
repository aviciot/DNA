-- ============================================================================
-- ISO Certification Management System - Database Migration
-- Phase 1: Foundation - Customer & Storage
-- ============================================================================

-- Enhance existing customers table with portal and storage fields
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_username VARCHAR(100) UNIQUE;
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_password_hash VARCHAR(255);
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS document_email VARCHAR(255);
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_type VARCHAR(50) DEFAULT 'local';
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500);
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_config JSONB;
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_enabled BOOLEAN DEFAULT false;
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS last_portal_login TIMESTAMP;

COMMENT ON COLUMN dna_app.customers.portal_username IS 'Username for customer portal access';
COMMENT ON COLUMN dna_app.customers.portal_password_hash IS 'Hashed password for portal login';
COMMENT ON COLUMN dna_app.customers.contact_email IS 'Primary contact email for communication';
COMMENT ON COLUMN dna_app.customers.document_email IS 'Email for sending/receiving documents';
COMMENT ON COLUMN dna_app.customers.storage_type IS 'Storage provider: local, google_drive, s3';
COMMENT ON COLUMN dna_app.customers.storage_path IS 'Path or URL to customer storage location';
COMMENT ON COLUMN dna_app.customers.storage_config IS 'Additional storage configuration (credentials, bucket names)';
COMMENT ON COLUMN dna_app.customers.portal_enabled IS 'Enable/disable customer portal access';
COMMENT ON COLUMN dna_app.customers.last_portal_login IS 'Last portal login timestamp';


-- ============================================================================
-- Table: customer_iso_plans
-- Customer's ISO certification plans
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_iso_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    iso_standard_id UUID NOT NULL REFERENCES dna_app.iso_standards(id) ON DELETE RESTRICT,
    plan_name VARCHAR(255),
    plan_status VARCHAR(50) DEFAULT 'active',
    template_selection_mode VARCHAR(50) DEFAULT 'all',
    target_completion_date DATE,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_active_iso_per_customer UNIQUE(customer_id, iso_standard_id)
);

CREATE INDEX idx_customer_iso_plans_customer ON dna_app.customer_iso_plans(customer_id);
CREATE INDEX idx_customer_iso_plans_iso ON dna_app.customer_iso_plans(iso_standard_id);
CREATE INDEX idx_customer_iso_plans_status ON dna_app.customer_iso_plans(plan_status);

COMMENT ON TABLE dna_app.customer_iso_plans IS 'Customer ISO certification plans';
COMMENT ON COLUMN dna_app.customer_iso_plans.plan_status IS 'Status: active, paused, completed, cancelled';
COMMENT ON COLUMN dna_app.customer_iso_plans.template_selection_mode IS 'Template selection: all or selective';


-- ============================================================================
-- Table: customer_iso_plan_templates
-- Selected templates for each ISO plan (used when selective mode)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_iso_plan_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES dna_app.templates(id) ON DELETE RESTRICT,
    included BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_plan_template UNIQUE(plan_id, template_id)
);

CREATE INDEX idx_plan_templates_plan ON dna_app.customer_iso_plan_templates(plan_id);
CREATE INDEX idx_plan_templates_template ON dna_app.customer_iso_plan_templates(template_id);

COMMENT ON TABLE dna_app.customer_iso_plan_templates IS 'Templates selected for each ISO plan (selective mode)';


-- ============================================================================
-- Table: customer_documents
-- Customer-specific documents generated from templates
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES dna_app.templates(id) ON DELETE RESTRICT,
    template_version INTEGER NOT NULL,
    template_name VARCHAR(500) NOT NULL,
    document_name VARCHAR(500) NOT NULL,
    document_type VARCHAR(100),
    iso_code VARCHAR(50),
    status VARCHAR(50) DEFAULT 'not_started',
    content JSONB NOT NULL,
    document_version INTEGER DEFAULT 1,
    completion_percentage INTEGER DEFAULT 0,
    mandatory_sections_total INTEGER DEFAULT 0,
    mandatory_sections_completed INTEGER DEFAULT 0,
    storage_path VARCHAR(500),
    exported_at TIMESTAMP,
    assigned_to INTEGER REFERENCES auth.users(id),
    created_by INTEGER REFERENCES auth.users(id),
    updated_by INTEGER REFERENCES auth.users(id),
    reviewed_by INTEGER REFERENCES auth.users(id),
    approved_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,
    due_date DATE,
    notes TEXT
);

CREATE INDEX idx_customer_documents_customer ON dna_app.customer_documents(customer_id);
CREATE INDEX idx_customer_documents_plan ON dna_app.customer_documents(plan_id);
CREATE INDEX idx_customer_documents_template ON dna_app.customer_documents(template_id);
CREATE INDEX idx_customer_documents_status ON dna_app.customer_documents(status);
CREATE INDEX idx_customer_documents_assigned ON dna_app.customer_documents(assigned_to);
CREATE INDEX idx_customer_documents_completion ON dna_app.customer_documents(completion_percentage);

COMMENT ON TABLE dna_app.customer_documents IS 'Customer documents generated from templates';
COMMENT ON COLUMN dna_app.customer_documents.template_version IS 'Snapshot: template version used';
COMMENT ON COLUMN dna_app.customer_documents.status IS 'Status: not_started, in_progress, pending_review, approved, rejected';
COMMENT ON COLUMN dna_app.customer_documents.content IS 'Document structure with fixed and fillable sections';


-- ============================================================================
-- Table: customer_tasks
-- Tasks and action items for documents or customer requirements
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    task_scope VARCHAR(50) NOT NULL DEFAULT 'document',
    section_id VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(50) DEFAULT 'medium',
    requires_evidence BOOLEAN DEFAULT false,
    evidence_description TEXT,
    evidence_format VARCHAR(100),
    evidence_uploaded BOOLEAN DEFAULT false,
    evidence_files JSONB,
    assigned_to INTEGER REFERENCES auth.users(id),
    due_date DATE,
    completed_at TIMESTAMP,
    completed_by INTEGER REFERENCES auth.users(id),
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    auto_generated BOOLEAN DEFAULT false
);

CREATE INDEX idx_customer_tasks_customer ON dna_app.customer_tasks(customer_id);
CREATE INDEX idx_customer_tasks_plan ON dna_app.customer_tasks(plan_id);
CREATE INDEX idx_customer_tasks_document ON dna_app.customer_tasks(document_id);
CREATE INDEX idx_customer_tasks_status ON dna_app.customer_tasks(status);
CREATE INDEX idx_customer_tasks_assigned ON dna_app.customer_tasks(assigned_to);
CREATE INDEX idx_customer_tasks_due ON dna_app.customer_tasks(due_date);
CREATE INDEX idx_customer_tasks_scope ON dna_app.customer_tasks(task_scope);
CREATE INDEX idx_customer_tasks_evidence ON dna_app.customer_tasks(requires_evidence, evidence_uploaded);

COMMENT ON TABLE dna_app.customer_tasks IS 'Tasks for documents, customers, or ISO plans';
COMMENT ON COLUMN dna_app.customer_tasks.task_type IS 'Type: fillable_section, evidence_required, review, custom, interview';
COMMENT ON COLUMN dna_app.customer_tasks.task_scope IS 'Scope: document, customer, iso_plan';
COMMENT ON COLUMN dna_app.customer_tasks.status IS 'Status: pending, in_progress, blocked, completed, cancelled';
COMMENT ON COLUMN dna_app.customer_tasks.priority IS 'Priority: low, medium, high, urgent';


-- ============================================================================
-- Table: customer_document_history
-- Version history and audit trail for documents
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_document_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content JSONB NOT NULL,
    change_summary TEXT,
    changed_by INTEGER REFERENCES auth.users(id),
    changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_document_history_document ON dna_app.customer_document_history(document_id);
CREATE INDEX idx_document_history_version ON dna_app.customer_document_history(document_id, version);

COMMENT ON TABLE dna_app.customer_document_history IS 'Document version history and audit trail';


-- ============================================================================
-- Table: customer_storage_files
-- Track all files stored for customers
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_storage_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE SET NULL,
    task_id UUID REFERENCES dna_app.customer_tasks(id) ON DELETE SET NULL,
    file_type VARCHAR(50) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    stored_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    description TEXT,
    uploaded_by INTEGER REFERENCES auth.users(id),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_storage_files_customer ON dna_app.customer_storage_files(customer_id);
CREATE INDEX idx_storage_files_document ON dna_app.customer_storage_files(document_id);
CREATE INDEX idx_storage_files_task ON dna_app.customer_storage_files(task_id);
CREATE INDEX idx_storage_files_type ON dna_app.customer_storage_files(file_type);

COMMENT ON TABLE dna_app.customer_storage_files IS 'Files stored for customers (evidence, exports, attachments)';
COMMENT ON COLUMN dna_app.customer_storage_files.file_type IS 'Type: evidence, export, attachment, interview_recording';


-- ============================================================================
-- Table: customer_interview_sessions
-- Track interview sessions for collecting customer information
-- ============================================================================
CREATE TABLE IF NOT EXISTS dna_app.customer_interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    session_name VARCHAR(255),
    interviewer_id INTEGER REFERENCES auth.users(id),
    session_status VARCHAR(50) DEFAULT 'active',
    questions_total INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    session_data JSONB,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_minutes INTEGER,
    notes TEXT
);

CREATE INDEX idx_interview_sessions_customer ON dna_app.customer_interview_sessions(customer_id);
CREATE INDEX idx_interview_sessions_document ON dna_app.customer_interview_sessions(document_id);
CREATE INDEX idx_interview_sessions_status ON dna_app.customer_interview_sessions(session_status);

COMMENT ON TABLE dna_app.customer_interview_sessions IS 'Interactive interview sessions for data collection';
COMMENT ON COLUMN dna_app.customer_interview_sessions.session_status IS 'Status: active, paused, completed, cancelled';


-- ============================================================================
-- View: v_customer_iso_progress
-- Calculate progress for each customer ISO plan
-- ============================================================================
CREATE OR REPLACE VIEW dna_app.v_customer_iso_progress AS
SELECT
    p.id as plan_id,
    p.customer_id,
    p.iso_standard_id,
    p.plan_name,
    p.plan_status,
    iso.code as iso_code,
    iso.name as iso_name,
    c.name as company_name,
    c.email as contact_email,
    -- Document metrics
    COUNT(DISTINCT d.id) as total_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END) as approved_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'in_progress' THEN d.id END) as in_progress_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'not_started' THEN d.id END) as not_started_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'pending_review' THEN d.id END) as pending_review_documents,
    -- Average document completion
    ROUND(COALESCE(AVG(d.completion_percentage), 0), 2) as avg_document_completion,
    -- Task metrics
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'pending' THEN t.id END) as pending_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'in_progress' THEN t.id END) as in_progress_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'blocked' THEN t.id END) as blocked_tasks,
    -- Evidence metrics
    COUNT(DISTINCT CASE WHEN t.requires_evidence = true THEN t.id END) as evidence_required_count,
    COUNT(DISTINCT CASE WHEN t.requires_evidence = true AND t.evidence_uploaded = true THEN t.id END) as evidence_uploaded_count,
    -- Progress calculations
    ROUND(
        CASE WHEN COUNT(DISTINCT d.id) > 0
        THEN (COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END)::NUMERIC / COUNT(DISTINCT d.id) * 100)
        ELSE 0 END, 2
    ) as document_approval_percentage,
    ROUND(
        CASE WHEN COUNT(DISTINCT t.id) > 0
        THEN (COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END)::NUMERIC / COUNT(DISTINCT t.id) * 100)
        ELSE 0 END, 2
    ) as task_completion_percentage,
    -- Overall progress (weighted: 60% docs + 40% tasks)
    ROUND(
        (CASE WHEN COUNT(DISTINCT d.id) > 0
         THEN (COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END)::NUMERIC / COUNT(DISTINCT d.id) * 60)
         ELSE 0 END) +
        (CASE WHEN COUNT(DISTINCT t.id) > 0
         THEN (COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END)::NUMERIC / COUNT(DISTINCT t.id) * 40)
         ELSE 0 END), 2
    ) as overall_progress_percentage,
    p.target_completion_date,
    p.started_at,
    p.completed_at,
    p.created_at
FROM dna_app.customer_iso_plans p
INNER JOIN dna_app.customers c ON p.customer_id = c.id
INNER JOIN dna_app.iso_standards iso ON p.iso_standard_id = iso.id
LEFT JOIN dna_app.customer_documents d ON p.id = d.plan_id
LEFT JOIN dna_app.customer_tasks t ON (d.id = t.document_id OR t.plan_id = p.id)
GROUP BY p.id, p.customer_id, p.iso_standard_id, p.plan_name, p.plan_status,
         iso.code, iso.name, c.name, c.email,
         p.target_completion_date, p.started_at, p.completed_at, p.created_at;

COMMENT ON VIEW dna_app.v_customer_iso_progress IS 'Progress metrics for each customer ISO plan';


-- ============================================================================
-- View: v_customer_overall_progress
-- High-level view of all customer progress
-- ============================================================================
CREATE OR REPLACE VIEW dna_app.v_customer_overall_progress AS
SELECT
    c.id as customer_id,
    c.name as company_name,
    c.email as contact_email,
    c.portal_enabled,
    c.last_portal_login,
    COUNT(DISTINCT p.id) as total_iso_plans,
    COUNT(DISTINCT CASE WHEN p.plan_status = 'active' THEN p.id END) as active_plans,
    COUNT(DISTINCT CASE WHEN p.plan_status = 'completed' THEN p.id END) as completed_plans,
    COUNT(DISTINCT d.id) as total_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END) as approved_documents,
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    ROUND(
        CASE WHEN COUNT(DISTINCT d.id) > 0
        THEN COALESCE(AVG(d.completion_percentage), 0)
        ELSE 0 END, 2
    ) as avg_document_completion,
    c.created_at as customer_since
FROM dna_app.customers c
LEFT JOIN dna_app.customer_iso_plans p ON c.id = p.customer_id
LEFT JOIN dna_app.customer_documents d ON p.id = d.plan_id
LEFT JOIN dna_app.customer_tasks t ON c.id = t.customer_id
GROUP BY c.id, c.name, c.email, c.portal_enabled, c.last_portal_login, c.created_at;

COMMENT ON VIEW dna_app.v_customer_overall_progress IS 'Overall progress for all customers across ISO plans';


-- ============================================================================
-- Migration Complete
-- ============================================================================
