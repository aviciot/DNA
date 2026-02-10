# ISO Certification Management System - Implementation Plan

## Overview
A comprehensive system for managing customer ISO certification projects, including template selection, document generation, task tracking, and progress monitoring.

## Business Flow

### 1. Customer ISO Assignment
```
Admin → Customer → Assign ISO Standards → Select Templates → Create Plan
```

**Example:**
- Customer: Acme Corp
- ISO 27001: All templates (default)
- ISO 9001: Only 2 out of 3 templates (selective)

### 2. Document Generation
```
ISO Plan Created → Auto-generate Documents from Templates → Each Document = Customer-specific instance
```

### 3. Task Management
```
Document Created → Auto-generate Tasks from Fillable Sections → Track Completion
```

### 4. Progress Tracking
```
Track: Document Status + Task Completion → Calculate Progress per ISO → Overall Customer Progress
```

---

## Database Schema

### Enhanced Customers Table

Add new fields to existing `customers` table for portal access and storage:

```sql
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_username VARCHAR(100) UNIQUE;
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_password_hash VARCHAR(255);
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);  -- Primary contact for communication
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS document_email VARCHAR(255);  -- Email for sending/receiving documents
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_type VARCHAR(50) DEFAULT 'local';  -- 'local', 'google_drive', 's3'
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500);  -- Path/URL to customer storage
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS storage_config JSONB;  -- Additional storage configuration (credentials, bucket names, etc.)
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS portal_enabled BOOLEAN DEFAULT false;  -- Enable/disable portal access
ALTER TABLE dna_app.customers ADD COLUMN IF NOT EXISTS last_portal_login TIMESTAMP;
```

**Storage Path Convention:**
- **Local**: `{base_storage_path}/customers/{customer_id}_{sanitized_company_name}/`
  - Example: `/var/dna/storage/customers/123_acme_corp/`
  - Subdirectories: `documents/`, `evidence/`, `exports/`, `temp/`
- **Google Drive**: Root folder ID stored in `storage_config`
- **S3**: Bucket + prefix stored in `storage_config`

### New Tables

#### 1. `customer_iso_plans`
Represents a customer's commitment to achieve an ISO certification.

```sql
CREATE TABLE dna_app.customer_iso_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    iso_standard_id UUID NOT NULL REFERENCES dna_app.iso_standards(id) ON DELETE RESTRICT,
    plan_name VARCHAR(255),  -- e.g., "ISO 27001 Certification 2026"
    plan_status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, cancelled
    template_selection_mode VARCHAR(50) DEFAULT 'all',  -- 'all' or 'selective'
    target_completion_date DATE,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by INTEGER REFERENCES dna_app.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(customer_id, iso_standard_id)  -- One active plan per ISO per customer
);

CREATE INDEX idx_customer_iso_plans_customer ON dna_app.customer_iso_plans(customer_id);
CREATE INDEX idx_customer_iso_plans_iso ON dna_app.customer_iso_plans(iso_standard_id);
CREATE INDEX idx_customer_iso_plans_status ON dna_app.customer_iso_plans(plan_status);
```

#### 2. `customer_iso_plan_templates`
Tracks which templates are included in each plan (for selective mode).

```sql
CREATE TABLE dna_app.customer_iso_plan_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES dna_app.catalog_templates(id) ON DELETE RESTRICT,
    included BOOLEAN DEFAULT true,  -- false = explicitly excluded
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plan_id, template_id)
);

CREATE INDEX idx_plan_templates_plan ON dna_app.customer_iso_plan_templates(plan_id);
```

#### 3. `customer_documents`
Customer-specific documents generated from templates. Each document is a snapshot of a template at a specific version.

```sql
CREATE TABLE dna_app.customer_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES dna_app.templates(id) ON DELETE RESTRICT,
    template_version INTEGER NOT NULL,  -- Snapshot: which template version was used
    template_name VARCHAR(500) NOT NULL,  -- Snapshot: template name at time of creation
    document_name VARCHAR(500) NOT NULL,  -- Can be customized by customer
    document_type VARCHAR(100),  -- policy, procedure, form, manual (copied from template)
    iso_code VARCHAR(50),  -- Snapshot: ISO code (e.g., "ISO 27001:2022")
    status VARCHAR(50) DEFAULT 'not_started',  -- not_started, in_progress, pending_review, approved, rejected
    content JSONB NOT NULL,  -- Document structure with filled sections
    -- Format: {
    --   "document_title": "...",
    --   "template_metadata": {...},  -- Original template metadata
    --   "fixed_sections": [...],  -- Read-only sections from template
    --   "fillable_sections": [  -- Sections to be filled
    --     {
    --       "id": "section_1",
    --       "title": "...",
    --       "type": "text|table|list|evidence",
    --       "is_mandatory": true,
    --       "placeholder": "...",
    --       "content": null,  -- Filled by user/customer
    --       "filled_at": null,
    --       "filled_by": null,
    --       "requires_evidence": false,
    --       "evidence_description": "..."
    --     }
    --   ]
    -- }
    document_version INTEGER DEFAULT 1,  -- Version of this customer document (increments on edits)
    completion_percentage INTEGER DEFAULT 0,  -- Auto-calculated based on filled mandatory sections
    mandatory_sections_total INTEGER DEFAULT 0,  -- Cached count
    mandatory_sections_completed INTEGER DEFAULT 0,  -- Cached count
    storage_path VARCHAR(500),  -- Path to exported document file
    exported_at TIMESTAMP,  -- Last export timestamp
    assigned_to INTEGER REFERENCES dna_app.users(id),  -- User responsible for completing this document
    created_by INTEGER REFERENCES dna_app.users(id),
    updated_by INTEGER REFERENCES dna_app.users(id),
    reviewed_by INTEGER REFERENCES dna_app.users(id),
    approved_by INTEGER REFERENCES dna_app.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,
    due_date DATE,
    notes TEXT  -- Internal notes
);

CREATE INDEX idx_customer_documents_customer ON dna_app.customer_documents(customer_id);
CREATE INDEX idx_customer_documents_plan ON dna_app.customer_documents(plan_id);
CREATE INDEX idx_customer_documents_template ON dna_app.customer_documents(template_id);
CREATE INDEX idx_customer_documents_status ON dna_app.customer_documents(status);
CREATE INDEX idx_customer_documents_assigned ON dna_app.customer_documents(assigned_to);
CREATE INDEX idx_customer_documents_completion ON dna_app.customer_documents(completion_percentage);
```

#### 4. `customer_tasks`
Tasks and action items for documents or general customer requirements. Supports evidence tracking.

```sql
CREATE TABLE dna_app.customer_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,  -- NULL for customer-level tasks
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,  -- NULL for customer-level tasks
    task_type VARCHAR(50) NOT NULL,  -- fillable_section, evidence_required, review, custom, interview
    task_scope VARCHAR(50) NOT NULL DEFAULT 'document',  -- document, customer, iso_plan
    section_id VARCHAR(255),  -- Reference to fillable section ID from template
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, blocked, completed, cancelled
    priority VARCHAR(50) DEFAULT 'medium',  -- low, medium, high, urgent
    requires_evidence BOOLEAN DEFAULT false,
    evidence_description TEXT,  -- What evidence is needed
    evidence_format VARCHAR(100),  -- document, log, screenshot, certificate, report
    evidence_uploaded BOOLEAN DEFAULT false,
    evidence_files JSONB,  -- Array of file references: [{"filename": "...", "storage_path": "...", "uploaded_at": "...", "uploaded_by": ...}]
    assigned_to INTEGER REFERENCES dna_app.users(id),
    due_date DATE,
    completed_at TIMESTAMP,
    completed_by INTEGER REFERENCES dna_app.users(id),
    created_by INTEGER REFERENCES dna_app.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    auto_generated BOOLEAN DEFAULT false  -- True if auto-generated from template
);

CREATE INDEX idx_customer_tasks_customer ON dna_app.customer_tasks(customer_id);
CREATE INDEX idx_customer_tasks_plan ON dna_app.customer_tasks(plan_id);
CREATE INDEX idx_customer_tasks_document ON dna_app.customer_tasks(document_id);
CREATE INDEX idx_customer_tasks_status ON dna_app.customer_tasks(status);
CREATE INDEX idx_customer_tasks_assigned ON dna_app.customer_tasks(assigned_to);
CREATE INDEX idx_customer_tasks_due ON dna_app.customer_tasks(due_date);
CREATE INDEX idx_customer_tasks_scope ON dna_app.customer_tasks(task_scope);
CREATE INDEX idx_customer_tasks_evidence ON dna_app.customer_tasks(requires_evidence, evidence_uploaded);
```

**Task Scope Levels:**
- **document**: Task specific to completing a single document (e.g., "Fill Quality Objectives section")
- **customer**: General task for customer onboarding/setup (e.g., "Collect company organization chart")
- **iso_plan**: Task related to entire ISO plan (e.g., "Schedule management review meeting")

#### 5. `customer_document_history`
Version history and audit trail for documents.

```sql
CREATE TABLE dna_app.customer_document_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content JSONB NOT NULL,  -- Snapshot of document at this version
    change_summary TEXT,
    changed_by INTEGER REFERENCES dna_app.users(id),
    changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_document_history_document ON dna_app.customer_document_history(document_id);
```

#### 6. `customer_storage_files`
Track all files stored for customers (evidence, exports, attachments).

```sql
CREATE TABLE dna_app.customer_storage_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE SET NULL,
    task_id UUID REFERENCES dna_app.customer_tasks(id) ON DELETE SET NULL,
    file_type VARCHAR(50) NOT NULL,  -- evidence, export, attachment, interview_recording
    original_filename VARCHAR(500) NOT NULL,
    stored_filename VARCHAR(500) NOT NULL,  -- Sanitized filename
    storage_path VARCHAR(1000) NOT NULL,  -- Full path or URL
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    description TEXT,
    uploaded_by INTEGER REFERENCES dna_app.users(id),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB  -- Additional file metadata
);

CREATE INDEX idx_storage_files_customer ON dna_app.customer_storage_files(customer_id);
CREATE INDEX idx_storage_files_document ON dna_app.customer_storage_files(document_id);
CREATE INDEX idx_storage_files_task ON dna_app.customer_storage_files(task_id);
CREATE INDEX idx_storage_files_type ON dna_app.customer_storage_files(file_type);
```

#### 7. `customer_interview_sessions`
Track interview sessions for collecting customer information interactively.

```sql
CREATE TABLE dna_app.customer_interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    document_id UUID REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    session_name VARCHAR(255),
    interviewer_id INTEGER REFERENCES dna_app.users(id),
    session_status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, cancelled
    questions_total INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    session_data JSONB,  -- Questions, answers, and notes
    -- Format: {
    --   "questions": [
    --     {
    --       "id": "q1",
    --       "section_id": "...",
    --       "question": "...",
    --       "answer": "...",
    --       "answered_at": "...",
    --       "requires_evidence": true,
    --       "evidence_uploaded": false
    --     }
    --   ]
    -- }
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_minutes INTEGER,  -- Auto-calculated
    notes TEXT
);

CREATE INDEX idx_interview_sessions_customer ON dna_app.customer_interview_sessions(customer_id);
CREATE INDEX idx_interview_sessions_document ON dna_app.customer_interview_sessions(document_id);
CREATE INDEX idx_interview_sessions_status ON dna_app.customer_interview_sessions(session_status);
```

### Views

#### `v_customer_iso_progress`
Calculate progress for each customer ISO plan with document and task metrics.

```sql
CREATE VIEW dna_app.v_customer_iso_progress AS
SELECT
    p.id as plan_id,
    p.customer_id,
    p.iso_standard_id,
    p.plan_name,
    p.plan_status,
    iso.code as iso_code,
    iso.name as iso_name,
    c.company_name,
    c.contact_email,
    -- Document metrics
    COUNT(DISTINCT d.id) as total_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END) as approved_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'in_progress' THEN d.id END) as in_progress_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'not_started' THEN d.id END) as not_started_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'pending_review' THEN d.id END) as pending_review_documents,
    -- Average document completion
    ROUND(AVG(d.completion_percentage), 2) as avg_document_completion,
    -- Task metrics (document-level and plan-level)
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
         iso.code, iso.name, c.company_name, c.contact_email,
         p.target_completion_date, p.started_at, p.completed_at, p.created_at;
```

#### `v_customer_overall_progress`
High-level view of all customer progress across all ISO plans.

```sql
CREATE VIEW dna_app.v_customer_overall_progress AS
SELECT
    c.id as customer_id,
    c.company_name,
    c.contact_email,
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
        THEN AVG(d.completion_percentage)
        ELSE 0 END, 2
    ) as avg_document_completion,
    c.created_at as customer_since
FROM dna_app.customers c
LEFT JOIN dna_app.customer_iso_plans p ON c.id = p.customer_id
LEFT JOIN dna_app.customer_documents d ON p.id = d.plan_id
LEFT JOIN dna_app.customer_tasks t ON c.id = t.customer_id
GROUP BY c.id, c.company_name, c.contact_email, c.portal_enabled, c.last_portal_login, c.created_at;
```

---

## API Endpoints

### Customer Management (Enhanced)

```
POST   /api/v1/customers
  Body: {
    company_name, address, phone, industry,
    contact_email, document_email,
    portal_enabled, portal_username, portal_password,  # Optional: auto-generate if not provided
    storage_type, storage_config,
    iso_standards: [  # Assign ISOs during creation
      {iso_standard_id, template_selection_mode, selected_template_ids}
    ]
  }

GET    /api/v1/customers
GET    /api/v1/customers/{customer_id}
PUT    /api/v1/customers/{customer_id}
DELETE /api/v1/customers/{customer_id}
POST   /api/v1/customers/{customer_id}/reset-portal-password  # Generate new random password
GET    /api/v1/customers/{customer_id}/portal-credentials  # Get username and temporary password
GET    /api/v1/customers/{customer_id}/storage-info  # Get storage paths and config
POST   /api/v1/customers/{customer_id}/initialize-storage  # Create folder structure
```

### Customer ISO Plans

```
POST   /api/v1/customers/{customer_id}/iso-plans
  Body: {
    iso_standard_id,
    plan_name,
    template_selection_mode: 'all' | 'selective',
    selected_template_ids: [...],  # Required if selective
    target_completion_date,
    auto_generate_documents: true  # Auto-generate on creation
  }

GET    /api/v1/customers/{customer_id}/iso-plans
GET    /api/v1/customers/{customer_id}/iso-plans/{plan_id}
PUT    /api/v1/customers/{customer_id}/iso-plans/{plan_id}
DELETE /api/v1/customers/{customer_id}/iso-plans/{plan_id}
POST   /api/v1/customers/{customer_id}/iso-plans/{plan_id}/templates  # Update template selection
GET    /api/v1/customers/{customer_id}/iso-plans/{plan_id}/progress  # Use v_customer_iso_progress view
POST   /api/v1/customers/{customer_id}/iso-plans/{plan_id}/generate-documents  # Regenerate documents
POST   /api/v1/customers/{customer_id}/iso-plans/{plan_id}/complete  # Mark plan as completed
```

### Customer Documents

```
GET    /api/v1/customer-documents?customer_id={id}&plan_id={id}&status={status}
GET    /api/v1/customer-documents/{document_id}
PUT    /api/v1/customer-documents/{document_id}
  Body: {
    content: {...},  # Updated fillable sections
    status,
    notes
  }

DELETE /api/v1/customer-documents/{document_id}
POST   /api/v1/customer-documents/{document_id}/submit-review  # Change status to pending_review
POST   /api/v1/customer-documents/{document_id}/approve  # Change status to approved
POST   /api/v1/customer-documents/{document_id}/reject  # Change status to rejected, add notes
GET    /api/v1/customer-documents/{document_id}/history  # Version history
POST   /api/v1/customer-documents/{document_id}/export  # Export to Word/PDF
GET    /api/v1/customer-documents/{document_id}/download  # Download exported file
POST   /api/v1/customer-documents/{document_id}/calculate-progress  # Recalculate completion percentage
```

### Customer Tasks (Document + Customer Level)

```
GET    /api/v1/tasks?customer_id={id}&document_id={id}&plan_id={id}&status={status}&assigned_to={user_id}
POST   /api/v1/tasks
  Body: {
    customer_id,
    document_id,  # Optional for customer-level tasks
    plan_id,  # Optional
    task_type, task_scope, title, description,
    priority, requires_evidence, evidence_description,
    assigned_to, due_date
  }

GET    /api/v1/tasks/{task_id}
PUT    /api/v1/tasks/{task_id}
DELETE /api/v1/tasks/{task_id}
POST   /api/v1/tasks/{task_id}/complete
POST   /api/v1/tasks/{task_id}/upload-evidence  # Upload evidence file
GET    /api/v1/tasks/{task_id}/evidence  # List evidence files
DELETE /api/v1/tasks/{task_id}/evidence/{file_id}  # Delete evidence file
```

### Interview Sessions (Interactive UI)

```
POST   /api/v1/customers/{customer_id}/interview-sessions
  Body: {
    document_id,  # Optional: interview for specific document
    session_name
  }

GET    /api/v1/customers/{customer_id}/interview-sessions
GET    /api/v1/interview-sessions/{session_id}
PUT    /api/v1/interview-sessions/{session_id}
  Body: {
    session_data: {
      questions: [{question, answer, answered_at, requires_evidence, evidence_uploaded}]
    }
  }

POST   /api/v1/interview-sessions/{session_id}/complete  # Mark session as completed
GET    /api/v1/interview-sessions/{session_id}/questions  # Get next question to ask
POST   /api/v1/interview-sessions/{session_id}/answer  # Submit answer to current question
  Body: {
    question_id, answer, evidence_files: [...]
  }

DELETE /api/v1/interview-sessions/{session_id}
```

### Storage & Files

```
POST   /api/v1/customers/{customer_id}/files/upload
  Body: multipart/form-data
  Fields: file, file_type, document_id, task_id, description

GET    /api/v1/customers/{customer_id}/files
GET    /api/v1/files/{file_id}
GET    /api/v1/files/{file_id}/download
DELETE /api/v1/files/{file_id}
```

---

## Business Logic

### 1. Customer Creation with ISO Assignment

```python
def create_customer_with_iso(customer_data, iso_assignments):
    """
    Create customer, initialize storage, generate credentials, and assign ISO plans.
    """
    # 1. Create customer record
    customer = create_customer({
        "company_name": customer_data.company_name,
        "contact_email": customer_data.contact_email,
        "document_email": customer_data.document_email or customer_data.contact_email,
        "storage_type": customer_data.storage_type or "local",
    })

    # 2. Generate portal credentials (if not provided)
    if not customer_data.portal_username:
        portal_username = generate_username(customer.company_name)  # e.g., "acme_corp_portal"
        portal_password = generate_random_password(16)  # Strong random password
        portal_password_hash = hash_password(portal_password)

        update_customer(customer.id, {
            "portal_username": portal_username,
            "portal_password_hash": portal_password_hash,
            "portal_enabled": customer_data.portal_enabled or False
        })

        # Send credentials to customer via email (if portal enabled)
        if customer_data.portal_enabled:
            send_portal_credentials_email(
                to=customer.contact_email,
                username=portal_username,
                password=portal_password  # Send once, securely
            )

    # 3. Initialize storage structure
    storage_path = initialize_customer_storage(customer)
    # Creates: {base}/customers/{id}_{name}/
    #   - documents/
    #   - evidence/
    #   - exports/
    #   - temp/

    update_customer(customer.id, {"storage_path": storage_path})

    # 4. Create ISO plans and generate documents
    for iso_assignment in iso_assignments:
        plan = create_iso_plan(customer.id, {
            "iso_standard_id": iso_assignment.iso_standard_id,
            "template_selection_mode": iso_assignment.mode,
            "selected_template_ids": iso_assignment.template_ids  # if selective
        })

        # Auto-generate documents
        generate_documents_for_plan(plan.id)

    return customer
```

### 2. Create ISO Plan Flow

```python
def create_iso_plan(customer_id, plan_data):
    """
    Create ISO plan, select templates, generate documents and tasks.
    """
    # 1. User selects customer + ISO standard
    # 2. User chooses template selection mode:
    #    - "All templates" (default)
    #    - "Selective" → User picks specific templates

    # 3. Create customer_iso_plan record
    plan = insert_customer_iso_plan({
        "customer_id": customer_id,
        "iso_standard_id": plan_data.iso_standard_id,
        "template_selection_mode": plan_data.template_selection_mode,
        "plan_status": "active",
        "started_at": NOW()
    })

    # 4. If selective, create customer_iso_plan_templates records
    if plan_data.template_selection_mode == "selective":
        for template_id in plan_data.selected_template_ids:
            insert_customer_iso_plan_template({
                "plan_id": plan.id,
                "template_id": template_id,
                "included": True
            })

    # 5. Auto-generate documents for all included templates
    generate_documents_for_plan(plan.id)

    return plan
```

### 3. Document Generation with Template Snapshot

When a plan is created or templates are selected, generate customer documents as snapshots of templates:

```python
def generate_documents_for_plan(plan_id):
    """
    Generate customer documents from selected templates.
    Each document is a snapshot of the template at a specific version.
    """
    plan = get_plan(plan_id)
    customer = get_customer(plan.customer_id)
    iso_standard = get_iso_standard(plan.iso_standard_id)

    # Get templates to include
    if plan.template_selection_mode == "all":
        templates = get_templates_for_iso(plan.iso_standard_id, active_only=True)
    else:
        templates = get_selected_templates_for_plan(plan_id)

    for template in templates:
        # Create document as snapshot
        document = create_customer_document({
            "customer_id": plan.customer_id,
            "plan_id": plan.id,
            "template_id": template.id,
            "template_version": template.version_number,  # SNAPSHOT
            "template_name": template.name,  # SNAPSHOT
            "document_name": f"{customer.company_name} - {template.name}",
            "document_type": template.document_type,
            "iso_code": iso_standard.code,  # SNAPSHOT
            "status": "not_started",
            "content": {
                "document_title": template.document_title,
                "template_metadata": template.metadata,
                "fixed_sections": template.fixed_sections,  # Read-only
                "fillable_sections": [
                    {
                        "id": section.id,
                        "title": section.title,
                        "type": section.type,
                        "is_mandatory": section.is_mandatory,
                        "placeholder": section.placeholder,
                        "content": None,  # To be filled
                        "filled_at": None,
                        "filled_by": None,
                        "requires_evidence": section.requires_evidence,
                        "evidence_description": section.evidence_description
                    }
                    for section in template.fillable_sections
                ]
            },
            "document_version": 1,
            "mandatory_sections_total": count_mandatory_sections(template),
            "mandatory_sections_completed": 0,
            "completion_percentage": 0
        })

        # Auto-generate tasks from fillable sections
        generate_tasks_for_document(document.id)

    # Also create customer-level and plan-level tasks
    generate_customer_level_tasks(plan)
```

### 4. Task Auto-Generation (Document, Plan, and Customer Level)

```python
def generate_tasks_for_document(document_id):
    """
    Auto-generate tasks from document's fillable sections.
    Creates document-level tasks for each mandatory or evidence-required section.
    """
    document = get_document(document_id)
    tasks = []

    for section in document.content["fillable_sections"]:
        # Create task for mandatory sections
        if section["is_mandatory"]:
            task = create_task({
                "customer_id": document.customer_id,
                "plan_id": document.plan_id,
                "document_id": document.id,
                "task_type": "fillable_section",
                "task_scope": "document",
                "section_id": section["id"],
                "title": f"Complete: {section['title']}",
                "description": section.get("placeholder") or f"Fill in the {section['type']} section",
                "priority": "high",
                "requires_evidence": section.get("requires_evidence", False),
                "evidence_description": section.get("evidence_description"),
                "auto_generated": True
            })
            tasks.append(task)

        # Create separate evidence task if evidence is required but section not mandatory
        elif section.get("requires_evidence"):
            task = create_task({
                "customer_id": document.customer_id,
                "plan_id": document.plan_id,
                "document_id": document.id,
                "task_type": "evidence_required",
                "task_scope": "document",
                "section_id": section["id"],
                "title": f"Provide Evidence: {section['title']}",
                "description": section.get("evidence_description") or "Upload required evidence",
                "priority": "medium",
                "requires_evidence": True,
                "evidence_description": section.get("evidence_description"),
                "auto_generated": True
            })
            tasks.append(task)

    return tasks


def generate_customer_level_tasks(plan):
    """
    Generate high-level tasks for customer onboarding and ISO plan setup.
    These are customer-level or plan-level tasks not tied to specific documents.
    """
    customer = get_customer(plan.customer_id)
    iso_standard = get_iso_standard(plan.iso_standard_id)

    # Common customer-level tasks for ISO certifications
    common_tasks = [
        {
            "title": "Collect Company Organization Chart",
            "description": "Obtain current organizational structure and reporting hierarchy",
            "task_type": "custom",
            "task_scope": "customer",
            "priority": "high",
            "requires_evidence": True,
            "evidence_description": "Organization chart (PDF, image, or document)",
            "evidence_format": "document"
        },
        {
            "title": "Collect List of Key Personnel and Roles",
            "description": "Document key personnel responsible for ISO implementation",
            "task_type": "custom",
            "task_scope": "customer",
            "priority": "high"
        },
        {
            "title": "Schedule Management Review Meeting",
            "description": f"Schedule initial management review for {iso_standard.name}",
            "task_type": "custom",
            "task_scope": "iso_plan",
            "priority": "medium"
        }
    ]

    # ISO-specific tasks
    if iso_standard.code.startswith("ISO 27001"):
        common_tasks.extend([
            {
                "title": "Inventory IT Assets",
                "description": "Create inventory of all IT assets (hardware, software, data)",
                "task_type": "custom",
                "task_scope": "iso_plan",
                "priority": "high",
                "requires_evidence": True,
                "evidence_description": "Asset inventory spreadsheet",
                "evidence_format": "document"
            },
            {
                "title": "Risk Assessment - Initial",
                "description": "Conduct initial information security risk assessment",
                "task_type": "custom",
                "task_scope": "iso_plan",
                "priority": "urgent",
                "requires_evidence": True,
                "evidence_description": "Risk assessment report",
                "evidence_format": "report"
            }
        ])
    elif iso_standard.code.startswith("ISO 9001"):
        common_tasks.extend([
            {
                "title": "Map Current Processes",
                "description": "Document existing quality management processes",
                "task_type": "custom",
                "task_scope": "iso_plan",
                "priority": "high"
            }
        ])

    # Create tasks
    for task_data in common_tasks:
        create_task({
            "customer_id": customer.id,
            "plan_id": plan.id if task_data["task_scope"] == "iso_plan" else None,
            "document_id": None,  # Not tied to specific document
            **task_data,
            "auto_generated": True
        })
```

### 5. Progress Calculation

Progress is calculated at multiple levels:

```python
def calculate_document_progress(document):
    """
    Calculate document completion based on mandatory sections filled.
    """
    mandatory_sections = [
        s for s in document.content["fillable_sections"]
        if s["is_mandatory"]
    ]

    if not mandatory_sections:
        return 100  # No mandatory sections = auto-complete

    filled_sections = [
        s for s in mandatory_sections
        if s["content"] is not None and s["content"] != ""
    ]

    completion = (len(filled_sections) / len(mandatory_sections)) * 100

    # Update document record
    update_document(document.id, {
        "mandatory_sections_total": len(mandatory_sections),
        "mandatory_sections_completed": len(filled_sections),
        "completion_percentage": round(completion, 2)
    })

    # Auto-change status based on completion
    if completion == 100 and document.status == "in_progress":
        update_document(document.id, {"status": "pending_review"})

    return round(completion, 2)


def calculate_plan_progress(plan):
    """
    Calculate ISO plan progress based on documents and tasks.
    Weighted: 60% document approval + 40% task completion
    """
    documents = get_plan_documents(plan)
    tasks = get_plan_tasks(plan)

    if not documents:
        return 0

    # Document progress
    approved_docs = [d for d in documents if d.status == "approved"]
    doc_progress = (len(approved_docs) / len(documents)) * 60

    # Task progress
    if tasks:
        completed_tasks = [t for t in tasks if t.status == "completed"]
        task_progress = (len(completed_tasks) / len(tasks)) * 40
    else:
        task_progress = 0

    overall_progress = doc_progress + task_progress
    return round(overall_progress, 2)


def calculate_customer_overall_progress(customer_id):
    """
    Calculate overall customer progress across all ISO plans.
    """
    plans = get_customer_plans(customer_id, status="active")

    if not plans:
        return 0

    plan_progresses = [calculate_plan_progress(p) for p in plans]
    avg_progress = sum(plan_progresses) / len(plan_progresses)

    return round(avg_progress, 2)
```

### 6. Interactive Interview Session Flow

The interview UI allows users to collect customer information interactively by guiding them through document questions.

```python
def start_interview_session(customer_id, document_id=None):
    """
    Start an interactive interview session to collect customer information.

    If document_id is provided: Interview focuses on that document's fillable sections.
    If document_id is None: General customer onboarding interview.
    """
    customer = get_customer(customer_id)

    # Prepare questions from document(s)
    questions = []

    if document_id:
        document = get_document(document_id)
        questions = prepare_document_questions(document)
    else:
        # General onboarding questions
        questions = prepare_onboarding_questions(customer)

    session = create_interview_session({
        "customer_id": customer_id,
        "document_id": document_id,
        "session_name": f"Interview: {document.document_name if document_id else 'Customer Onboarding'}",
        "session_status": "active",
        "questions_total": len(questions),
        "questions_answered": 0,
        "session_data": {"questions": questions},
        "started_at": NOW()
    })

    return session


def prepare_document_questions(document):
    """
    Convert document fillable sections into interview questions.
    """
    questions = []

    for section in document.content["fillable_sections"]:
        question = {
            "id": f"q_{section['id']}",
            "section_id": section["id"],
            "question": generate_friendly_question(section),  # Convert placeholder to question
            "section_title": section["title"],
            "section_type": section["type"],  # text, table, list, evidence
            "is_mandatory": section["is_mandatory"],
            "answer": None,
            "answered_at": None,
            "requires_evidence": section.get("requires_evidence", False),
            "evidence_description": section.get("evidence_description"),
            "evidence_uploaded": False,
            "evidence_files": []
        }
        questions.append(question)

    return questions


def generate_friendly_question(section):
    """
    Convert technical section placeholder into user-friendly interview question.
    Uses simple rules or LLM to rephrase.
    """
    if section["type"] == "text":
        return f"Please provide: {section['title']}"
    elif section["type"] == "table":
        return f"Please fill in the table for: {section['title']}"
    elif section["type"] == "list":
        return f"Please list: {section['title']}"
    elif section["type"] == "evidence":
        return f"Please upload evidence for: {section['title']}"

    # Fallback
    return section.get("placeholder") or section["title"]


def submit_interview_answer(session_id, question_id, answer, evidence_files=None):
    """
    Submit answer to interview question and update document content.
    """
    session = get_interview_session(session_id)

    # Find question
    question = next(
        (q for q in session.session_data["questions"] if q["id"] == question_id),
        None
    )

    if not question:
        raise ValueError(f"Question {question_id} not found")

    # Update question with answer
    question["answer"] = answer
    question["answered_at"] = NOW()

    # Handle evidence files
    if evidence_files and question["requires_evidence"]:
        uploaded_files = []
        for file in evidence_files:
            file_record = store_evidence_file(
                customer_id=session.customer_id,
                document_id=session.document_id,
                file=file
            )
            uploaded_files.append(file_record)

        question["evidence_files"] = uploaded_files
        question["evidence_uploaded"] = True

    # Update session
    questions_answered = sum(1 for q in session.session_data["questions"] if q["answer"])
    update_interview_session(session_id, {
        "session_data": session.session_data,
        "questions_answered": questions_answered
    })

    # If document interview, update document content
    if session.document_id:
        update_document_section_from_answer(
            session.document_id,
            question["section_id"],
            answer
        )

        # Recalculate document progress
        document = get_document(session.document_id)
        calculate_document_progress(document)

    return question


def update_document_section_from_answer(document_id, section_id, answer):
    """
    Update document fillable section with interview answer.
    """
    document = get_document(document_id)

    # Find and update section
    for section in document.content["fillable_sections"]:
        if section["id"] == section_id:
            section["content"] = answer
            section["filled_at"] = NOW()
            # filled_by can be set from current user context

    # Save updated content
    update_document(document_id, {
        "content": document.content,
        "status": "in_progress"  # Auto-change to in_progress
    })
```

---

## Frontend UI Components

### 1. Enhanced Customer Creation/Edit Modal

**Customer Information Section:**
- Company name, address, phone, industry (existing)
- Contact email (primary contact for communication)
- Document email (email for sending/receiving documents)
- Portal access toggle (Enable customer portal?)
  - If enabled:
    - Portal username (auto-suggest: `{company_name}_portal`)
    - Password (auto-generate button or manual entry)
    - Show generated credentials with copy buttons

**Storage Configuration Section:**
- Storage type dropdown: Local (default), Google Drive (future), S3 (future)
- If Local: Display path that will be created (read-only preview)
  - Example: `/var/dna/storage/customers/123_acme_corp/`
- Storage initialization button (creates folder structure)

**ISO Assignment Section (Optional during creation):**
- "+ Add ISO Standard" button
- For each ISO:
  - ISO standard selector
  - Template selection mode radio:
    - ○ All templates (default)
    - ○ Select specific templates
  - If selective: Checklist of available templates
  - Target completion date

**Actions:**
- Save Customer (creates customer + storage + ISO plans + documents)
- Save & Start Interview (saves then launches interview session)

### 2. Customer Detail View

**Overview Tab:**
- Customer info card (company details, contact, storage path)
- Portal credentials card (show username, reset password button)
- Overall progress gauge (across all ISO plans)
- Quick stats: Total plans, Total documents, Total tasks

**ISO Plans Tab:**
- List of customer's ISO plans
- For each plan:
  - ISO code/name
  - Progress bar (overall_progress_percentage from view)
  - Document count (total / approved)
  - Task count (completed / total)
  - Evidence count (uploaded / required)
  - Target completion date
  - Status badge (active, paused, completed, cancelled)
  - Actions: View Details, Edit, Complete, Delete
- "+ New ISO Plan" button

**Documents Tab:**
- Filterable document list
  - Filter by: ISO plan, Status, Assigned user
- For each document:
  - Document name
  - Template name + version badge (v2)
  - ISO code badge
  - Status badge (not_started, in_progress, pending_review, approved)
  - Progress bar (completion_percentage)
  - Assigned user avatar
  - Due date
  - Actions: Edit, Start Interview, Submit Review, Approve/Reject, Export

**Tasks Tab:**
- Kanban board or list view toggle
- Columns: Pending / In Progress / Blocked / Completed
- Filters: Document, Assigned user, Priority, Requires evidence
- For each task:
  - Title
  - Document name (if document-level)
  - Scope badge (document/customer/iso_plan)
  - Priority indicator
  - Evidence required icon + count
  - Assigned user
  - Due date
  - Actions: Edit, Upload Evidence, Complete

**Files & Evidence Tab:**
- File browser showing customer storage
- Grouped by: Documents, Evidence, Exports, Temp
- Upload area (drag & drop or browse)
- For each file:
  - Filename
  - Type badge (evidence, export, attachment)
  - Associated document/task (if any)
  - File size
  - Upload date & user
  - Actions: Download, Delete

### 3. Create ISO Plan Modal (Standalone or during customer creation)
- Select ISO standard
- Plan name (optional, auto-suggest: "{ISO Code} Certification {Year}")
- Template selection mode radio:
  - ○ All templates (default)
  - ○ Select specific templates
- If selective mode:
  - Checklist of available templates for that ISO (show version numbers)
  - Template count indicator: "3 of 10 templates selected"
- Target completion date picker
- Auto-generate documents checkbox (default: true)
- Actions: Create Plan, Create & Start Interview

### 4. ISO Plan Detail View
- **Header:**
  - ISO code/name badge
  - Status badge with dropdown to change (Active, Paused, Completed, Cancelled)
  - Progress ring chart (overall_progress_percentage)
  - Target completion date
  - Actions: Edit, Complete Plan, Delete

- **Tabs:**
  - **Overview**: Key metrics cards
    - Documents: Total / Approved / In Progress / Not Started
    - Tasks: Total / Completed / Pending / Blocked
    - Evidence: Required / Uploaded / Missing
    - Progress trend chart (last 30 days)

  - **Documents**: List of plan documents with filters

  - **Tasks**: Kanban board filtered to this plan

  - **Timeline**: Activity feed (documents created, completed, tasks done, evidence uploaded)

### 5. Document Editor (Manual Filling)

Split-view interface for filling documents manually:

**Left Panel: Document Structure**
- Fixed sections (read-only, collapsed/expandable)
- Fillable sections list with indicators:
  - ✓ Completed (green)
  - ⚠ In Progress (yellow)
  - ○ Not Started (gray)
  - 📎 Requires Evidence (icon)
  - ⭐ Mandatory (icon)
- Click section to scroll to editor

**Right Panel: Content Editor**
- Section-by-section editor:
  - Section title and description
  - Input field (based on type):
    - **Text**: Rich text editor
    - **Table**: Inline table editor (add/remove rows)
    - **List**: Bulleted list editor
    - **Evidence**: File upload area
  - Placeholder/guidance text
  - Evidence requirements (if applicable)
  - Related task indicator (link to task)
  - Mark as complete checkbox (auto-saves)

**Top Bar:**
- Document name (editable)
- Status dropdown (Draft, In Progress, Submit for Review)
- Progress indicator: "3 of 8 mandatory sections completed (37%)"
- Actions:
  - Save Draft
  - Submit for Review
  - Export to Word/PDF
  - Start Interview (switch to interview mode)

### 6. Interactive Interview UI ⭐ KEY FEATURE

Wizard-style interface for collecting customer information interactively:

**Interview Session Screen:**

**Top: Progress Header**
- Session name: "Interview: Quality Management Policy"
- Progress bar: "Question 5 of 12 (42%)"
- Time elapsed: "15 minutes"
- Actions: Save & Pause, Complete Interview

**Main Area: Question Display**

Card-based, one question at a time:

```
┌─────────────────────────────────────────────────────────┐
│ Question 5 of 12                                   [⭐ MANDATORY] │
│                                                           │
│ Quality Objectives                                        │
│ ────────────────────────────────────────────────────     │
│                                                           │
│ Please provide your company's quality objectives for     │
│ this year. Include measurable targets and timelines.     │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [Rich text editor or input field based on type]    │ │
│ │                                                     │ │
│ │                                                     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ 📎 Evidence Required: Supporting documentation           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [Drag & drop file upload area]                      │ │
│ │ Upload quality objectives document (PDF, Word, Excel)│ │
│ │                                                     │ │
│ │ [Select File]  or drag & drop here                 │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ Uploaded: quality_objectives_2026.pdf (✓)                │
│                                                           │
│ [← Previous]          [Skip]          [Next →]           │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Large, easy-to-read question text
- Contextual input fields (text, table, file upload) based on section type
- Evidence upload integrated directly
- Visual indicators for mandatory questions (⭐)
- Real-time save (answers saved immediately)
- Navigation: Previous, Next, Skip (for non-mandatory)
- Question index on the side (click to jump)
- Answers automatically populate document sections in background

**Interview Session List:**
- View past/active interview sessions
- Resume incomplete sessions
- Session summary: Date, Duration, Questions answered, Completion %

### 7. Document Review & Approval Workflow

**Pending Review State:**
- Document submitted by user
- Reviewer sees banner: "This document is pending your review"
- Side-by-side view:
  - Left: Template structure (expected)
  - Right: Filled content (actual)
- Review checklist (auto-generated or custom):
  - ☐ All mandatory sections completed
  - ☐ Evidence provided where required
  - ☐ Content aligns with ISO requirements
  - ☐ Formatting is correct
- Add review notes/comments
- Actions: Approve, Request Changes (with notes), Reject

**Approved State:**
- Green checkmark badge
- Timestamp and approver name
- Export options:
  - Export to Word
  - Export to PDF
  - Send to customer email

### 8. Task Detail Modal

**Task Information:**
- Title, Description
- Task type badge (fillable_section, evidence_required, custom)
- Scope badge (document, customer, iso_plan)
- Status dropdown
- Priority dropdown
- Assigned user selector
- Due date picker

**If Document-Level Task:**
- Link to document: "View Document →"
- Link to section: "Jump to Section →"

**If Evidence Required:**
- Evidence description
- Evidence format (document, log, screenshot, etc.)
- Upload area (drag & drop)
- Uploaded files list:
  - Filename, size, upload date, uploaded by
  - Preview (for images) or download link
  - Delete button

**Activity Log:**
- Task created by X on date
- Task assigned to Y on date
- Evidence uploaded by Z on date
- Task completed by A on date

**Actions:**
- Save Changes
- Upload Evidence
- Mark as Completed
- Delete Task

### 9. Evidence & File Management

**Evidence Dashboard:**
- List all evidence required for customer
- Filter by: ISO plan, Document, Status (uploaded/missing)
- For each evidence requirement:
  - Description
  - Related document/task
  - Status badge (Uploaded ✓ / Missing ✗)
  - Upload date & user (if uploaded)
  - Actions: View, Upload, Delete

**File Browser:**
- Tree view of customer storage:
  - 📁 documents/
  - 📁 evidence/
  - 📁 exports/
  - 📁 temp/
- Upload button (with type selector)
- File list with thumbnails
- Bulk actions: Download selected, Delete selected

### 10. Progress Dashboard (Customer Level)

**Overview Cards:**
- Total ISO Plans (active/completed)
- Total Documents (approved / total)
- Total Tasks (completed / total)
- Evidence Collected (uploaded / required)

**Charts:**
- ISO Plan Progress (pie chart for each plan)
- Document Completion Trend (line chart over time)
- Task Status Breakdown (stacked bar chart)
- Upcoming Deadlines (list with countdown)

**Recent Activity Feed:**
- "Document 'Quality Policy' approved by John Doe - 2 hours ago"
- "Evidence uploaded for task 'Risk Assessment' - 5 hours ago"
- "ISO 27001 Plan 45% complete - 1 day ago"

---

## Implementation Phases

### Phase 1: Foundation - Customer & Storage (Week 1-2)

**Database:**
- [ ] Alter `customers` table (add portal, storage, email fields)
- [ ] Create `customer_iso_plans` table
- [ ] Create `customer_iso_plan_templates` table
- [ ] Create `customer_documents` table with template snapshot fields
- [ ] Create `customer_tasks` table (multi-scope)
- [ ] Create `customer_storage_files` table
- [ ] Create `customer_document_history` table
- [ ] Create `customer_interview_sessions` table
- [ ] Create views: `v_customer_iso_progress`, `v_customer_overall_progress`

**Backend API:**
- [ ] Enhanced Customer API (create/edit with ISO assignment, storage initialization)
- [ ] Portal credentials generation (username, random password)
- [ ] Storage service layer (local folder creation, path management)
- [ ] Customer storage initialization endpoint

**Frontend:**
- [ ] Enhanced Customer Creation/Edit Modal
  - Portal credentials section
  - Storage configuration section
  - ISO assignment section (optional during creation)
- [ ] Customer storage info display

**Deliverable:** Create customers with portal credentials and storage, ready for ISO assignment.

---

### Phase 2: ISO Plans & Document Generation (Week 3-4)

**Backend API:**
- [ ] ISO Plans API (create, read, update, delete)
- [ ] Template selection logic (all vs selective mode)
- [ ] Document generation from templates (snapshot with version tracking)
- [ ] Task auto-generation from templates
  - Document-level tasks
  - Customer-level tasks
  - ISO-specific tasks (27001, 9001, etc.)
- [ ] Progress calculation logic

**Frontend:**
- [ ] Create ISO Plan Modal
- [ ] ISO Plans Tab (in customer detail view)
- [ ] ISO Plan Detail View
  - Overview tab with metrics
  - Documents list
  - Tasks list
  - Timeline
- [ ] Progress indicators and charts

**Deliverable:** Assign ISO standards to customers, generate documents and tasks automatically.

---

### Phase 3: Document Editor & Manual Filling (Week 5)

**Backend API:**
- [ ] Customer Documents API (get, update, delete)
- [ ] Update document section content
- [ ] Calculate document completion percentage
- [ ] Document status workflow (draft → in_progress → pending_review → approved/rejected)
- [ ] Document history/versioning

**Frontend:**
- [ ] Document Editor UI (split view)
  - Structure panel (left)
  - Content editor (right)
  - Section-based editing
- [ ] Different input types (text, table, list, evidence)
- [ ] Progress indicator per document
- [ ] Save draft and submit for review
- [ ] Document history viewer

**Deliverable:** Users can manually fill documents section by section.

---

### Phase 4: Interactive Interview UI ⭐ (Week 6-7)

**Backend API:**
- [ ] Interview Sessions API (create, get, update, delete)
- [ ] Generate interview questions from document sections
- [ ] Submit interview answers
- [ ] Auto-update document sections from answers
- [ ] Handle evidence uploads during interview

**Frontend:**
- [ ] Interview Session Wizard UI
  - One question at a time (card-based)
  - Progress tracking
  - Evidence upload integrated
  - Previous/Next/Skip navigation
- [ ] Interview session list (active, completed, paused)
- [ ] Resume interview functionality
- [ ] Real-time save of answers
- [ ] Success animation on completion

**Deliverable:** Friendly, interactive way to collect customer information.

---

### Phase 5: Task Management & Evidence Tracking (Week 8-9)

**Backend API:**
- [ ] Tasks API (CRUD for all task scopes)
- [ ] Evidence file upload/download
- [ ] Link files to tasks and documents
- [ ] Task completion with evidence validation
- [ ] Bulk task operations

**Frontend:**
- [ ] Task Board (Kanban view)
  - Drag & drop between columns
  - Filters (document, scope, assigned user, priority)
- [ ] Task Detail Modal
  - Evidence upload area
  - File preview/download
  - Activity log
- [ ] Evidence Dashboard
  - List all evidence requirements
  - Upload status tracking
- [ ] File Browser (customer storage tree view)

**Deliverable:** Comprehensive task and evidence management system.

---

### Phase 6: Review & Approval Workflow (Week 10)

**Backend API:**
- [ ] Submit document for review endpoint
- [ ] Approve/reject document endpoints
- [ ] Add review notes/comments
- [ ] Document export to Word/PDF
- [ ] Email notifications (document submitted, approved, rejected)

**Frontend:**
- [ ] Document review interface
  - Side-by-side comparison (template vs filled)
  - Review checklist
  - Add comments
- [ ] Approve/Reject buttons with confirmation
- [ ] Export options (Word, PDF)
- [ ] Send to customer email
- [ ] Review status indicators

**Deliverable:** Complete document approval workflow.

---

### Phase 7: Progress Dashboard & Reporting (Week 11)

**Backend API:**
- [ ] Progress calculation endpoints (customer, plan, document levels)
- [ ] Activity feed API
- [ ] Reports generation (PDF summaries)
- [ ] Analytics endpoints (completion trends, bottlenecks)

**Frontend:**
- [ ] Customer Overall Progress Dashboard
  - Overview cards
  - Progress charts (pie, line, bar)
  - Recent activity feed
  - Upcoming deadlines
- [ ] ISO Plan Progress Dashboard
- [ ] Document completion trend chart
- [ ] Export reports (PDF, Excel)

**Deliverable:** Visual progress tracking and reporting.

---

### Phase 8: Integration & Polish (Week 12-13)

**Integration:**
- [ ] Integrate customer ISO management into existing Admin page
- [ ] Update CustomerManagement component with ISO assignment
- [ ] Add quick links from documents to interviews
- [ ] Breadcrumb navigation across all views

**Polish:**
- [ ] Loading states and skeletons
- [ ] Error handling and user feedback
- [ ] Confirmation dialogs for destructive actions
- [ ] Tooltips and help text
- [ ] Responsive design (mobile-friendly)
- [ ] Dark mode support
- [ ] Accessibility (ARIA labels, keyboard navigation)

**Testing:**
- [ ] Unit tests (backend logic)
- [ ] Integration tests (API endpoints)
- [ ] E2E tests (critical user flows)
- [ ] Load testing (document generation performance)
- [ ] Bug fixes and edge cases

**Documentation:**
- [ ] API documentation (Swagger/OpenAPI)
- [ ] User guide (how to use the system)
- [ ] Admin guide (setup, configuration)

**Deliverable:** Production-ready ISO certification management system.

---

### Phase 9: Future Enhancements (Post-Launch)

**Automation:**
- [ ] Email integration (send/receive documents via email)
- [ ] Customer portal (login, view progress, fill documents)
- [ ] LLM-powered chat assistant (guide customers through questions)
- [ ] Auto-generate document drafts using AI
- [ ] Smart evidence validation (check uploaded files match requirements)

**Advanced Features:**
- [ ] Google Drive integration for storage
- [ ] AWS S3 integration for storage
- [ ] Calendar integration (sync due dates, meetings)
- [ ] Notification system (Slack, Teams, Email)
- [ ] Audit trail (detailed activity logs)
- [ ] Role-based permissions (viewer, editor, approver)
- [ ] Multi-language support
- [ ] Template marketplace (share templates across organizations)

**Deliverable:** Scalable, automated ISO certification platform.

---

## Storage Architecture

### Local Storage Structure

When a customer is created with `storage_type='local'`, the system creates the following folder structure:

```
{base_storage_path}/customers/
└── {customer_id}_{sanitized_company_name}/
    ├── documents/              # Exported document files (Word, PDF)
    │   ├── iso_27001/
    │   │   ├── quality_policy_v1.docx
    │   │   ├── quality_policy_v1.pdf
    │   │   └── ...
    │   └── iso_9001/
    │       └── ...
    ├── evidence/               # Evidence files uploaded by users
    │   ├── task_{task_id}/
    │   │   ├── asset_inventory.xlsx
    │   │   ├── risk_assessment.pdf
    │   │   └── ...
    │   └── document_{document_id}/
    │       └── ...
    ├── exports/                # Generated reports, exports
    │   ├── progress_report_2026-02-10.pdf
    │   └── ...
    └── temp/                   # Temporary files (auto-cleanup after 7 days)
        └── ...
```

**Naming Convention:**
- **Customer folder**: `{customer_id}_{company_name_lowercase_no_spaces}/`
  - Example: `123_acme_corp/`
- **Files**: `{sanitized_name}_v{version}.{ext}`
  - Example: `quality_management_policy_v2.pdf`

**Configuration:**
```python
# settings.py
CUSTOMER_STORAGE_BASE_PATH = os.getenv("CUSTOMER_STORAGE_PATH", "/var/dna/storage/customers")
CUSTOMER_STORAGE_MAX_FILE_SIZE_MB = 50  # Max file upload size
CUSTOMER_STORAGE_ALLOWED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".csv"]
```

### Future Storage Providers

**Google Drive:**
- Create root folder per customer
- Store folder ID in `storage_config`
- Use Google Drive API for upload/download
- Share folder with customer email

**AWS S3:**
- Bucket per environment (dev, prod)
- Customer prefix: `customers/{customer_id}/`
- Store bucket name and prefix in `storage_config`
- Use pre-signed URLs for secure downloads

**Storage Service Layer:**
```python
class StorageService:
    @staticmethod
    async def initialize_storage(customer: Customer):
        """Initialize storage based on customer.storage_type"""
        if customer.storage_type == "local":
            return await LocalStorageProvider.initialize(customer)
        elif customer.storage_type == "google_drive":
            return await GoogleDriveProvider.initialize(customer)
        elif customer.storage_type == "s3":
            return await S3StorageProvider.initialize(customer)

    @staticmethod
    async def upload_file(customer: Customer, file: UploadFile, path: str):
        """Upload file to customer storage"""
        provider = get_storage_provider(customer.storage_type)
        return await provider.upload(customer, file, path)

    @staticmethod
    async def download_file(customer: Customer, path: str):
        """Download file from customer storage"""
        provider = get_storage_provider(customer.storage_type)
        return await provider.download(customer, path)
```

---

## Key Decisions

### 1. Customer Portal Credentials
**Decision:** Auto-generate portal credentials during customer creation
- **Username**: `{company_name}_portal` (sanitized, unique)
- **Password**: Random 16-character strong password (auto-generated)
- **Rationale**: Simplifies onboarding, ensures security, future-proofs for customer portal feature
- Portal enabled/disabled by toggle (default: disabled for MVP)
- Send credentials via email once (not stored in plain text)

### 2. Storage Architecture
**Decision:** Local filesystem storage for MVP, extensible for future providers
- **MVP**: Local folder structure (`/var/dna/storage/customers/{id}_{name}/`)
- **Future**: Google Drive, AWS S3, Azure Blob
- **Rationale**:
  - Local storage is simple, fast, no external dependencies
  - Folder structure mirrors customer organization (documents, evidence, exports, temp)
  - Storage service layer abstracts provider, easy to add new providers later
- **Trade-off**: Local storage requires backup strategy, but good enough for MVP

### 3. Template Snapshot Approach
**Decision:** Copy template content as snapshot when generating documents
- Document stores: `template_id`, `template_version`, `template_name`, `iso_code`
- **Rationale**:
  - Customer documents remain stable even if template changes
  - Clear audit trail (which template version was used)
  - Customers don't get unexpected changes mid-project
- **Trade-off**: Can't auto-update documents if template improves, but this is intentional (stability > auto-update)

### 4. Task Scopes (Document, Customer, ISO Plan)
**Decision:** Support three task scopes
- **document**: Task tied to specific document section (e.g., "Fill Quality Objectives")
- **customer**: General onboarding task (e.g., "Collect org chart")
- **iso_plan**: ISO-specific task (e.g., "Schedule management review")
- **Rationale**: Some tasks are document-specific, others are customer-wide or ISO-wide
- Auto-generate tasks for all three scopes during plan creation

### 5. Interactive Interview UI as Primary UX
**Decision:** Prioritize interview-style data collection over manual document editing
- **Interview UI**: Wizard-style, one question at a time, friendly, guided
- **Manual Editor**: Available but secondary (for power users)
- **Rationale**:
  - Most users prefer guided questions over free-form editing
  - Interview format reduces errors, ensures consistency
  - Better user experience for non-technical customers
  - Easier to integrate AI assistance later (chatbot can guide interview)
- Interview answers automatically populate document sections in background

### 6. Evidence Tracking System
**Decision:** Treat evidence as first-class entities with dedicated tracking
- Tasks can require evidence (boolean flag)
- Evidence files tracked in `customer_storage_files` table
- Link evidence to tasks AND documents
- **Rationale**:
  - Evidence collection is critical for ISO compliance
  - Needs visibility and tracking separate from general files
  - Some evidence applies to multiple documents/tasks
- Dashboard shows evidence required vs uploaded (compliance metric)

### 7. Progress Calculation (Weighted)
**Decision:** Multi-level weighted progress calculation
- **Document level**: % of mandatory sections filled (0-100%)
- **Plan level**: 60% document approval + 40% task completion
- **Customer level**: Average of all active plan progresses
- **Rationale**:
  - Document approval alone doesn't reflect work done
  - Tasks (especially evidence collection) are significant effort
  - Weighting reflects typical ISO project breakdown
- Progress auto-calculated on document/task updates

### 8. Template Selection Modes
**Decision:** Support both "all" and "selective" modes
- **All templates** (default): Include all active templates for ISO
- **Selective**: User picks specific templates (checkboxes)
- **Rationale**:
  - Most customers need all templates (simpler workflow)
  - Some customers may have existing policies (can exclude templates)
  - Flexibility without complication

### 9. Document Status Workflow
**Decision:** Simple linear workflow with optional states
- States: `not_started` → `in_progress` → `pending_review` → `approved` / `rejected`
- Auto-transition:
  - `not_started` → `in_progress` (when first section filled)
  - `in_progress` → `pending_review` (when 100% complete + user submits)
- **Rationale**: Clear, intuitive workflow that matches real-world process
- Rejected documents go back to `in_progress` with reviewer notes

### 10. Document Versioning
**Decision:** Simple version incrementing on significant changes
- Version increments on: Save, Submit for review, Approval
- Keep full history in `customer_document_history` table
- **Rationale**:
  - Audit trail for compliance
  - Ability to restore previous versions
  - Track who changed what and when
- Version number displayed in UI (e.g., "Quality Policy v3")

### 11. Multi-User Collaboration (MVP)
**Decision:** Basic assignment model for MVP, expand later
- Assign documents to users (responsible for completing)
- Assign tasks to users (responsible for completion)
- Track: created_by, updated_by, reviewed_by, approved_by
- **Rationale**:
  - Simple enough for MVP
  - Covers 80% of use cases
  - Can add real-time collaboration later (operational transforms, conflict resolution)
- **Future**: Real-time co-editing, comments, mentions

### 12. Customer ISO Plan Uniqueness
**Decision:** One ACTIVE plan per ISO per customer
- Constraint: `UNIQUE(customer_id, iso_standard_id)` on active plans
- Allow multiple plans with different statuses (completed, cancelled)
- **Rationale**:
  - Prevents confusion (which plan is current?)
  - Customer can renew ISO later (complete old plan, create new one)
- Example: "ISO 27001 (2023) - Completed" + "ISO 27001 (2026) - Active"

### 13. Evidence Upload During Interview
**Decision:** Allow evidence upload inline during interview questions
- If question requires evidence, show upload area immediately
- Evidence automatically links to task + document + question
- **Rationale**:
  - Reduces friction (collect evidence when asking question)
  - Better user flow (don't make users come back later)
  - Higher evidence collection rate
- Interview can't complete if mandatory evidence missing

### 14. Storage Provider Extensibility
**Decision:** Abstract storage behind service layer from day 1
- Storage service interface: `initialize()`, `upload()`, `download()`, `delete()`, `list()`
- Providers: `LocalStorageProvider`, `GoogleDriveProvider` (future), `S3Provider` (future)
- Customer.storage_type determines provider
- **Rationale**:
  - Easy to add new providers without changing application code
  - Some customers may require specific storage (Google Workspace customers → Drive)
  - Testable (mock storage provider in tests)
- **Trade-off**: Slight complexity upfront, but worth it for future flexibility

---

## Sample User Scenarios

### Scenario 1: Complete Customer Onboarding with Interview (Recommended Flow)

**Goal:** Onboard new customer "Acme Corp" for ISO 27001 certification using interactive interview.

```
1. Admin clicks "Create Customer" in Customer Management
2. Fills in customer info:
   - Company name: Acme Corp
   - Contact email: john@acme.com
   - Document email: compliance@acme.com
3. Enables portal access:
   - System auto-generates username: "acme_corp_portal"
   - System auto-generates password: "Xk9#mP2$vN8@qL4!"
   - Portal enabled: Yes
4. Configures storage:
   - Storage type: Local (default)
   - System shows path: "/var/dna/storage/customers/123_acme_corp/"
5. Assigns ISO 27001:
   - Template selection: All templates (15 templates)
   - Target completion: 2026-12-31
6. Clicks "Save & Start Interview"

System actions:
- Creates customer record
- Creates local storage folder structure
- Sends portal credentials email to john@acme.com
- Creates ISO 27001 plan
- Generates 15 documents (snapshots of templates v2)
- Generates 120 tasks (document-level, customer-level, ISO-specific)
- Launches interview session for first document "Information Security Policy"

7. Interview UI loads:
   - Shows: "Question 1 of 8"
   - Question: "Please describe your company's information security objectives"
   - Admin asks customer and types answer
   - Question 2 requires evidence: "Upload your current org chart"
   - Admin uploads "acme_org_chart.pdf"
   - Continues through 8 questions
   - Interview completes, document auto-filled to 100%
   - Status changes to "Pending Review"

8. Admin reviews document:
   - Clicks "Review" button
   - Sees side-by-side comparison
   - All sections filled correctly
   - Evidence uploaded
   - Clicks "Approve"

9. Progress dashboard updates:
   - 1 of 15 documents approved (6.7%)
   - 8 of 120 tasks completed (6.7%)
   - Overall progress: 6.7%

10. Repeat interview for remaining 14 documents over next few weeks
```

### Scenario 2: Selective Template Assignment (Partial ISO Compliance)

**Goal:** Customer "Beta Inc" only needs specific ISO 9001 templates, not all.

```
1. Admin creates customer "Beta Inc"
2. Assigns ISO 9001
3. Chooses "Selective" template mode
4. Template checklist appears:
   ☑ Quality Manual
   ☑ Document Control Procedure
   ☑ Internal Audit Procedure
   ☐ Corrective Action Procedure (unchecked - customer has this)
   ☐ Management Review Procedure (unchecked - customer has this)
   ☑ Training Procedure
   (5 templates selected)
5. System generates only 5 documents (not all 10)
6. Reduces scope for smaller projects

Result:
- Customer sees only relevant documents
- Progress calculation based on 5 documents (not 10)
- Customer's existing procedures recognized (not duplicated)
```

### Scenario 3: Evidence Collection Flow

**Goal:** Collect required evidence for ISO 27001 "Risk Assessment" document.

```
1. User opens Tasks dashboard
2. Filters by "Requires Evidence" = True
3. Sees task: "Provide Evidence: Risk Assessment Report"
   - Status: Pending
   - Evidence description: "Risk assessment report covering information assets, threats, and controls"
   - Evidence format: Report
4. User clicks "Upload Evidence"
5. Drags "acme_risk_assessment_2026.pdf" to upload area
6. File uploads to: /storage/customers/123_acme_corp/evidence/task_456/
7. System creates record in customer_storage_files:
   - file_type: "evidence"
   - task_id: 456
   - document_id: 789
8. Task automatically marked as completed
9. Document "Risk Assessment" completion increases from 80% to 100%
10. Evidence dashboard shows: "23 of 25 evidence items collected (92%)"
```

### Scenario 4: Multi-Document Interview Session

**Goal:** Efficiently collect information for multiple related documents in one session.

```
1. Admin notices 5 policy documents are "Not Started"
2. Clicks "Start Bulk Interview" (future feature)
3. System generates interview session with questions from all 5 documents
4. Interview combines 35 questions intelligently:
   - Groups related questions
   - Skips duplicates (e.g., "Company name" asked once)
   - Orders by document dependencies
5. Admin completes interview in 45 minutes
6. System distributes answers to correct documents
7. All 5 documents auto-filled and marked "In Progress"

Result:
- 5 documents progressed from 0% to 85% in single session
- More efficient than editing each document separately
- Better user experience (feels like conversation, not form-filling)
```

### Scenario 5: Customer Portal Access (Future)

**Goal:** Customer accesses portal to view progress and upload evidence.

```
1. Customer receives email with portal credentials
   - Username: acme_corp_portal
   - Password: Xk9#mP2$vN8@qL4!
   - Portal URL: https://dna.example.com/portal
2. Customer logs in
3. Dashboard shows:
   - ISO 27001 Plan: 45% complete
   - 7 of 15 documents approved
   - 5 tasks assigned to customer (evidence upload)
4. Customer clicks "Upload Evidence for Asset Inventory"
5. Uploads "acme_asset_inventory.xlsx"
6. System notifies admin: "Customer uploaded evidence for Asset Inventory"
7. Admin reviews and marks task as complete

Result:
- Customer can track progress independently
- Customer can upload evidence without admin involvement
- Reduces back-and-forth communication
```

### Scenario 6: Document Rejection and Rework

**Goal:** Reviewer rejects document, assignee fixes issues and resubmits.

```
1. User submits "Quality Policy" for review
   - Status: Pending Review
2. Manager reviews document:
   - Notices "Quality Objectives" section is incomplete
   - Notices evidence is wrong format (PNG instead of PDF)
3. Manager clicks "Request Changes"
4. Adds note: "Quality Objectives need specific measurable targets. Re-upload evidence as PDF."
5. Document status changes back to "In Progress"
6. User receives notification: "Quality Policy rejected - changes requested"
7. User opens document:
   - Sees reviewer notes
   - Updates "Quality Objectives" section with specific metrics
   - Re-uploads evidence as PDF
8. User clicks "Resubmit for Review"
9. Manager reviews again:
   - Issues resolved
   - Clicks "Approve"
10. Document status: Approved
11. Version incremented: v1 → v2

Result:
- Clear feedback loop
- Audit trail of changes (version history)
- Document quality improved through review process
```

### Scenario 7: Progress Tracking and Reporting

**Goal:** Admin needs to report ISO certification progress to management.

```
1. Admin opens Customer "Acme Corp" dashboard
2. Views overall progress: 67% complete
3. Clicks "Progress Dashboard"
4. Sees breakdown:
   - Documents: 10 of 15 approved (67%)
   - Tasks: 85 of 120 completed (71%)
   - Evidence: 20 of 25 collected (80%)
5. Charts show:
   - Pie chart: Document status breakdown
   - Line chart: Progress trend (last 30 days) - steady climb
   - Bar chart: Tasks by status
6. Clicks "Export Report"
7. System generates PDF report:
   - Executive summary
   - Progress metrics
   - Document completion list
   - Evidence status
   - Upcoming deadlines
   - Activity timeline
8. Admin emails report to management

Result:
- Clear visibility into project status
- Data-driven insights (bottlenecks, trends)
- Professional reporting for stakeholders
```

### Scenario 8: ISO-Specific Task Auto-Generation

**Goal:** System automatically creates ISO 27001-specific tasks.

```
When admin assigns ISO 27001 to customer:

System auto-generates customer-level tasks:
1. "Collect Company Organization Chart" (high priority, requires evidence)
2. "Collect List of Key Personnel and Roles" (high priority)

System auto-generates ISO-specific tasks:
3. "Inventory IT Assets" (high priority, requires evidence: asset inventory spreadsheet)
4. "Risk Assessment - Initial" (urgent, requires evidence: risk assessment report)
5. "Schedule Management Review Meeting" (medium priority)

When admin assigns ISO 9001 to customer:

System auto-generates different ISO-specific tasks:
1. "Map Current Processes" (high priority)
2. "Identify Quality Metrics" (high priority)
3. "Schedule Management Review" (medium priority)

Result:
- Relevant tasks created automatically based on ISO standard
- Ensures no critical steps are missed
- Tailored to each ISO's specific requirements
```

---

## Design Clarifications & Remaining Questions

### ✅ Resolved Through Design

1. **User Roles** → Decided: Basic assignment model for MVP
   - All authenticated users can view/edit assigned documents
   - Admins can create plans and approve documents
   - Future: Add distinct roles (Admin, Manager, Team Member, Viewer)

2. **Notifications** → Decided: Email notifications for key events (Phase 6)
   - Document submitted for review
   - Document approved/rejected
   - Portal credentials sent on customer creation
   - Future: Slack, Teams integration

3. **Document Templates** → Decided: Copy template structure as snapshot
   - No customization before generation (keep it simple)
   - Future: Allow template customization per customer

4. **Multiple ISO Plans** → Decided: One ACTIVE plan per ISO per customer
   - Can have multiple completed/cancelled plans
   - Example: ISO 27001 (2023) - Completed, ISO 27001 (2026) - Active

5. **Evidence Management** → Decided: First-class evidence tracking
   - Evidence tracked in `customer_storage_files` table
   - Linked to tasks AND documents
   - Evidence dashboard for visibility

6. **Integration with existing `documents` table** → Decided: Keep separate
   - Current `documents` table is for reference/uploaded documents
   - New `customer_documents` table is for generated ISO documents
   - Different purposes, no conflict

### ❓ Remaining Questions for Validation

1. **Storage Base Path Configuration:**
   - Where should customer files be stored? (e.g., `/var/dna/storage/customers/`)
   - Should this be configurable per environment (dev, staging, prod)?
   - What's the backup strategy for local storage?

2. **Portal Password Security:**
   - Send password via email (one-time) or require admin to share securely?
   - Force password change on first login?
   - Password reset flow (email link, admin reset, security questions)?

3. **Document Export Format:**
   - Export to Word only, or also PDF?
   - Should exports preserve formatting exactly as template, or allow custom styling?
   - Who can export documents (anyone, or only after approval)?

4. **Interview Session Resumption:**
   - If user closes interview halfway, how long should session remain active?
   - Auto-save frequency during interview (every answer, every 30 seconds)?
   - Allow multiple users to contribute to same interview session?

5. **Task Due Date Assignment:**
   - Should tasks have due dates auto-assigned based on plan target_completion_date?
   - Formula: Spread tasks evenly over plan duration?
   - Or leave due dates empty for admin to assign manually?

6. **Evidence Validation:**
   - Should system validate evidence files (e.g., check file type matches requirement)?
   - Size limits per file type?
   - Virus scanning for uploaded files?

7. **Document Completion Threshold:**
   - 100% completion = all mandatory sections filled?
   - Or require approval before considering document "complete"?
   - Can document be approved if non-mandatory sections are empty?

8. **Customer Portal Scope (Future):**
   - What can customers do in portal?
     - View progress? (Yes)
     - Edit documents? (Risky - could break compliance)
     - Upload evidence? (Yes)
     - Chat with support? (Nice to have)
   - Should customers see internal notes/comments?

9. **Multi-Tenancy:**
   - Is this system single-tenant (one company managing their customers)?
   - Or multi-tenant (multiple consulting firms using same platform)?
   - Impacts: Data isolation, branding, user management

10. **Email Integration (Future):**
    - Inbound: Parse emails and auto-attach to documents/tasks?
    - Outbound: Send documents via email directly from system?
    - Email templates for notifications?
    - Email tracking (opened, clicked)?

### 💡 Nice-to-Have Features (Post-MVP)

1. **AI-Powered Features:**
   - Auto-generate document drafts from templates using LLM
   - Chatbot to guide customers through interview (instead of admin)
   - Smart evidence validation (check if uploaded file matches requirement description)
   - Suggest answers based on similar customers

2. **Collaboration:**
   - Real-time co-editing of documents (like Google Docs)
   - Comments and mentions (@user)
   - Activity feed per document (who changed what)

3. **Workflow Automation:**
   - Auto-assign tasks based on rules (e.g., "All risk assessment tasks → Security Team")
   - Auto-escalate overdue tasks
   - Approval workflows with multiple reviewers

4. **Integrations:**
   - Calendar sync (Google Calendar, Outlook) for due dates
   - Slack notifications for task assignments
   - Jira integration for task management
   - DocuSign integration for approvals

5. **Analytics:**
   - Time-to-completion per document type
   - Bottleneck analysis (which documents take longest?)
   - Team productivity metrics
   - Customer health scores

6. **Template Marketplace:**
   - Share templates across organizations
   - Community-contributed templates
   - Template ratings and reviews

---

## Next Steps

### Immediate Actions (Before Implementation)

1. **Review & Validate Plan:**
   - Review entire plan with stakeholders
   - Validate database schema (tables, fields, indexes)
   - Confirm UI/UX mockups match expectations
   - Answer remaining questions (see "Remaining Questions" section)

2. **Technical Decisions:**
   - Confirm storage base path for customer files
   - Decide on portal password delivery method
   - Confirm document export formats (Word, PDF, both)
   - Set file upload limits and allowed extensions

3. **Priority & Scope:**
   - Confirm Phase 1-8 scope (13 weeks)
   - Decide if any phases can be deprioritized
   - Identify must-have vs nice-to-have features
   - Set target launch date

### Implementation Approach

**Option A: Sequential (Safer, Predictable)**
- Complete Phase 1, then Phase 2, then Phase 3, etc.
- Test thoroughly after each phase
- Demo progress to stakeholders weekly
- **Timeline**: 13 weeks (3 months)

**Option B: Parallel (Faster, More Risk)**
- Backend team works on Phases 1-2 (database, API)
- Frontend team works on Phases 3-4 (UI mockups, components)
- Integrate and test in Phase 5-6
- **Timeline**: 8-9 weeks (2 months)

**Recommendation**: Option A (sequential) for MVP
- Lower risk of integration issues
- Easier to adjust based on feedback
- Better for small teams

### Ready to Start?

Once you approve this plan, I can begin with:

**Phase 1: Foundation - Customer & Storage**
- Create database migration SQL
- Implement enhanced Customer API (create/edit with ISO assignment)
- Build portal credentials generation
- Build storage initialization service
- Create frontend: Enhanced Customer Creation/Edit Modal

**Deliverable (Week 1-2):** Ability to create customers with portal credentials and storage, ready for ISO assignment.

### How to Proceed

1. **If plan looks good**: Say "Approved, proceed with Phase 1" and I'll start implementation
2. **If changes needed**: Point out specific sections to revise
3. **If questions**: Ask anything about the architecture, design, or implementation

### Documentation Status

- ✅ Database schema defined (7 new tables, 2 views)
- ✅ API endpoints specified (30+ endpoints)
- ✅ Business logic documented (6 core flows)
- ✅ UI components designed (10 major components)
- ✅ Implementation phases planned (8 phases, 13 weeks)
- ✅ Key decisions documented (14 decisions)
- ✅ User scenarios defined (8 scenarios)
- ⏳ Remaining: Answer clarification questions, get approval

---

**This plan is comprehensive and ready for implementation. Let me know if you'd like to proceed or if you have any questions or changes!**
