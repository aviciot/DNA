# Phase 3 Database Reference Guide

Quick reference for using the new Phase 3 database tables.

---

## 📋 **Table: customer_configuration**

### Purpose
Store customer-specific and global configuration templates (emails, branding, preferences).

### Key Columns
```sql
id                  UUID        Primary key
customer_id         INTEGER     NULL = global default, INTEGER = customer-specific
config_type         VARCHAR     Type: 'welcome_email', 'evidence_request', etc.
config_key          VARCHAR     Specific key within type
config_value        JSONB       Configuration content (subject, body, etc.)
is_template         BOOLEAN     Is this a reusable template?
template_variables  JSONB       Available variables for interpolation
use_ai_phrasing     BOOLEAN     Enable AI content generation (future)
is_default          BOOLEAN     Is this the default config?
is_active           BOOLEAN     Is this configuration active?
```

### Common Queries

**Get default welcome email template:**
```sql
SELECT * FROM dna_app.customer_configuration
WHERE customer_id IS NULL
  AND config_type = 'welcome_email'
  AND is_default = true;
```

**Get customer-specific configuration:**
```sql
SELECT * FROM dna_app.customer_configuration
WHERE customer_id = 123
  AND config_type = 'welcome_email'
  AND is_active = true;
```

**Create custom configuration for customer:**
```sql
INSERT INTO dna_app.customer_configuration (
    customer_id,
    config_type,
    config_key,
    config_value,
    is_template,
    template_variables
) VALUES (
    123,  -- customer_id
    'welcome_email',
    'custom_welcome',
    '{"subject": "Welcome {{company_name}}!", "body": "..."}'::jsonb,
    true,
    '[{"name": "company_name", "type": "string"}]'::jsonb
);
```

### Variable Interpolation Example
```json
{
  "subject": "Welcome to DNA, {{company_name}}!",
  "body": "Dear {{primary_contact}},\n\nYou have {{template_count}} templates assigned..."
}
```

Variables will be replaced at runtime:
- `{{company_name}}` → "Acme Corporation"
- `{{primary_contact}}` → "John Smith"
- `{{template_count}}` → "5"

---

## 📋 **Table: customer_tasks (Enhanced)**

### New Columns Added
```sql
is_ignored           BOOLEAN     Task marked as irrelevant (not deleted)
ignored_at           TIMESTAMP   When task was ignored
ignored_by           INTEGER     Who ignored the task
ignore_reason        TEXT        Why task was ignored
created_manually_by  INTEGER     Who manually created this task
manual_task_context  TEXT        Additional context for manual tasks
```

### Existing Important Columns
```sql
id                   UUID        Task ID
customer_id          INTEGER     Customer reference
plan_id              UUID        ISO plan reference
document_id          UUID        Document reference (if applicable)
task_type            VARCHAR     Type of task
task_scope           VARCHAR     'customer', 'plan', 'document', 'question'
title                VARCHAR     Task title
status               VARCHAR     'pending', 'in_progress', 'completed', etc.
priority             VARCHAR     'urgent', 'high', 'medium', 'low'
auto_generated       BOOLEAN     System-generated (true) or manual (false)
requires_evidence    BOOLEAN     Does this task need evidence?
```

### Common Queries

**Get all active tasks for customer (excluding ignored):**
```sql
SELECT * FROM dna_app.customer_tasks
WHERE customer_id = 123
  AND (is_ignored = false OR is_ignored IS NULL)
  AND status NOT IN ('completed', 'cancelled')
ORDER BY priority DESC, due_date ASC;
```

**Create manual task:**
```sql
INSERT INTO dna_app.customer_tasks (
    customer_id,
    plan_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    auto_generated,
    created_manually_by,
    manual_task_context,
    assigned_to,
    due_date
) VALUES (
    123,                                    -- customer_id
    'uuid-of-plan'::UUID,                  -- plan_id (optional)
    'follow_up',                           -- task_type
    'customer',                            -- task_scope
    'Follow-up call with Acme Corp',       -- title
    'Check on progress...',                -- description
    'medium',                              -- priority
    false,                                 -- auto_generated
    1,                                     -- created_manually_by (admin user id)
    'Customer requested additional help',  -- manual_task_context
    1,                                     -- assigned_to
    '2026-02-20'::DATE                     -- due_date
);
```

**Mark task as ignored:**
```sql
UPDATE dna_app.customer_tasks
SET
    is_ignored = true,
    ignored_at = NOW(),
    ignored_by = 1,  -- admin user id
    ignore_reason = 'Template removed from plan'
WHERE id = 'uuid-of-task'::UUID;
```

**Get task statistics for customer:**
```sql
SELECT
    COUNT(*) FILTER (WHERE is_ignored = false) as active_tasks,
    COUNT(*) FILTER (WHERE status = 'completed' AND is_ignored = false) as completed_tasks,
    COUNT(*) FILTER (WHERE status = 'pending' AND is_ignored = false) as pending_tasks,
    COUNT(*) FILTER (WHERE is_ignored = true) as ignored_tasks
FROM dna_app.customer_tasks
WHERE customer_id = 123;
```

---

## 📋 **Table: customer_iso_plans (Enhanced)**

### New Columns Added
```sql
is_ignored      BOOLEAN     Plan marked as irrelevant (not deleted)
ignored_at      TIMESTAMP   When plan was ignored
ignored_by      INTEGER     Who ignored the plan
ignore_reason   TEXT        Why plan was ignored
```

### Common Queries

**Get active ISO plans for customer:**
```sql
SELECT * FROM dna_app.customer_iso_plans
WHERE customer_id = 123
  AND (is_ignored = false OR is_ignored IS NULL)
  AND plan_status = 'active';
```

**Mark plan as ignored:**
```sql
UPDATE dna_app.customer_iso_plans
SET
    is_ignored = true,
    ignored_at = NOW(),
    ignored_by = 1,
    ignore_reason = 'Customer changed compliance scope'
WHERE id = 'uuid-of-plan'::UUID;
```

---

## 📋 **Table: task_resolutions**

### Purpose
Track how tasks are resolved (answers provided, evidence uploaded, approvals, etc.)

### Key Columns
```sql
id                   UUID        Resolution ID
task_id              UUID        Task being resolved
resolution_type      VARCHAR     'answer_provided', 'evidence_uploaded', 'approved', etc.
resolution_data      JSONB       Resolution details
is_final             BOOLEAN     Is this the final resolution?
requires_approval    BOOLEAN     Does this need admin approval?
approved_at          TIMESTAMP   When approved
approved_by          INTEGER     Who approved
resolved_by          INTEGER     Who resolved
quality_score        INTEGER     1-5 quality rating
completeness_score   INTEGER     0-100 completeness
notes                TEXT        Additional notes
```

### Common Queries

**Submit answer for question task:**
```sql
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    resolved_by
) VALUES (
    'uuid-of-task'::UUID,
    'answer_provided',
    '{"answer": "Acme Corporation", "question_placeholder": "organization_name"}'::jsonb,
    true,
    1  -- user id
);

-- Also update task status
UPDATE dna_app.customer_tasks
SET status = 'completed', completed_at = NOW()
WHERE id = 'uuid-of-task'::UUID;
```

**Submit evidence for review:**
```sql
INSERT INTO dna_app.task_resolutions (
    task_id,
    resolution_type,
    resolution_data,
    is_final,
    requires_approval,
    resolved_by
) VALUES (
    'uuid-of-task'::UUID,
    'evidence_uploaded',
    '{
        "file_path": "/uploads/customer_123/evidence/backup_policy.pdf",
        "file_name": "backup_policy.pdf",
        "file_size": 1234567
    }'::jsonb,
    false,  -- Not final until approved
    true,   -- Requires admin approval
    123     -- customer user id
);

-- Update task to under_review
UPDATE dna_app.customer_tasks
SET status = 'under_review'
WHERE id = 'uuid-of-task'::UUID;
```

**Approve resolution:**
```sql
UPDATE dna_app.task_resolutions
SET
    is_final = true,
    approved_at = NOW(),
    approved_by = 1,  -- admin user id
    quality_score = 5,
    completeness_score = 100
WHERE id = 'uuid-of-resolution'::UUID;

-- Update task to completed
UPDATE dna_app.customer_tasks
SET status = 'completed', completed_at = NOW()
WHERE id = (SELECT task_id FROM dna_app.task_resolutions WHERE id = 'uuid-of-resolution'::UUID);
```

**Get all resolutions for a task:**
```sql
SELECT * FROM dna_app.task_resolutions
WHERE task_id = 'uuid-of-task'::UUID
ORDER BY resolved_at DESC;
```

---

## 📋 **Table: task_templates**

### Purpose
Reusable templates for creating manual tasks quickly.

### Key Columns
```sql
id                      UUID        Template ID
template_name           VARCHAR     Template name
task_type               VARCHAR     Type of task
task_scope              VARCHAR     'customer', 'plan', 'document', 'question'
default_title           VARCHAR     Default title (supports variables)
default_description     TEXT        Default description
default_priority        VARCHAR     Default priority
default_due_in_days     INTEGER     Default due date offset
is_system_template      BOOLEAN     System vs custom template
is_active               BOOLEAN     Is template active?
```

### Common Queries

**List available task templates:**
```sql
SELECT * FROM dna_app.task_templates
WHERE is_active = true
ORDER BY task_scope, template_name;
```

**Get template for creating task:**
```sql
SELECT * FROM dna_app.task_templates
WHERE template_name = 'Schedule Kickoff Meeting'
  AND is_active = true;
```

**Create task from template:**
```sql
WITH template AS (
    SELECT * FROM dna_app.task_templates
    WHERE id = 'uuid-of-template'::UUID
)
INSERT INTO dna_app.customer_tasks (
    customer_id,
    task_type,
    task_scope,
    title,
    description,
    priority,
    due_date,
    auto_generated,
    created_manually_by
)
SELECT
    123,  -- customer_id
    t.task_type,
    t.task_scope,
    REPLACE(t.default_title, '{{company_name}}', 'Acme Corp'),
    t.default_description,
    t.default_priority,
    CURRENT_DATE + (t.default_due_in_days || ' days')::INTERVAL,
    false,
    1  -- admin user id
FROM template t;

-- Update usage count
UPDATE dna_app.task_templates
SET
    usage_count = usage_count + 1,
    last_used_at = NOW()
WHERE id = 'uuid-of-template'::UUID;
```

**Create custom task template:**
```sql
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
    created_by
) VALUES (
    'Custom Review Task',
    'Review specific section of documentation',
    'review',
    'document',
    'Review {{section_name}} for {{company_name}}',
    'Please review the {{section_name}} section...',
    'medium',
    5,
    false,  -- Custom template
    1       -- admin user id
);
```

---

## 📋 **View: v_customer_iso_progress**

### Purpose
Provides aggregated progress tracking per customer-ISO relationship.

### Columns
```sql
id                      UUID        Plan ID
customer_id             INTEGER     Customer ID
iso_standard_id         UUID        ISO standard ID
iso_code                VARCHAR     ISO code (e.g., "ISO 27001:2022" or "stand_alone")
iso_name                VARCHAR     ISO name
plan_name               VARCHAR     Plan name
plan_status             VARCHAR     Plan status
target_completion_date  DATE        Target date
total_templates         BIGINT      Total templates assigned
completed_templates     BIGINT      Templates completed
in_progress_templates   BIGINT      Templates in progress
total_tasks             BIGINT      Total active tasks (excluding ignored)
completed_tasks         BIGINT      Completed tasks
in_progress_tasks       BIGINT      In progress tasks
pending_tasks           BIGINT      Pending tasks
ignored_tasks           BIGINT      Ignored tasks (for audit)
progress_percentage     INTEGER     Overall progress (0-100)
```

### Common Queries

**Get customer overview:**
```sql
SELECT
    iso_code,
    iso_name,
    total_templates,
    completed_templates,
    total_tasks,
    completed_tasks,
    progress_percentage,
    target_completion_date
FROM dna_app.v_customer_iso_progress
WHERE customer_id = 123
ORDER BY progress_percentage DESC;
```

**Get customers behind schedule:**
```sql
SELECT
    c.name as customer_name,
    v.iso_code,
    v.progress_percentage,
    v.target_completion_date,
    v.pending_tasks
FROM dna_app.v_customer_iso_progress v
JOIN dna_app.customers c ON v.customer_id = c.id
WHERE v.target_completion_date < CURRENT_DATE + INTERVAL '30 days'
  AND v.progress_percentage < 50
ORDER BY v.target_completion_date ASC;
```

---

## 🏷️ **Special ISO: stand_alone**

### Purpose
For templates not associated with any specific ISO standard.

### Usage

**Reference in queries:**
```sql
-- Get stand_alone ISO ID
SELECT id FROM dna_app.iso_standards WHERE code = 'stand_alone';
-- Result: 00000000-0000-0000-0000-000000000001
```

**Create plan with stand_alone templates:**
```sql
INSERT INTO dna_app.customer_iso_plans (
    customer_id,
    iso_standard_id,
    plan_name,
    plan_status
) VALUES (
    123,
    '00000000-0000-0000-0000-000000000001'::UUID,  -- stand_alone ISO
    'Custom Templates',
    'active'
);
```

---

## 🔄 **Common Workflows**

### **Workflow 1: Create Customer with Welcome Email**

```sql
-- 1. Create customer
INSERT INTO dna_app.customers (name, email, contact_person, status, created_by)
VALUES ('Acme Corp', 'admin@acme.com', 'John Smith', 'active', 1)
RETURNING id;

-- 2. Get welcome email template
SELECT config_value FROM dna_app.customer_configuration
WHERE customer_id IS NULL
  AND config_type = 'welcome_email'
  AND is_default = true;

-- 3. Interpolate variables and send email (application logic)
-- Replace: {{company_name}}, {{primary_contact}}, {{customer_email}}, etc.
```

### **Workflow 2: Assign ISO Plan and Generate Tasks**

```sql
-- 1. Create ISO plan
INSERT INTO dna_app.customer_iso_plans (
    customer_id, iso_standard_id, plan_name, target_completion_date, created_by
) VALUES (
    123, 'uuid-of-iso'::UUID, 'ISO 27001 Compliance', '2026-12-31', 1
)
RETURNING id as plan_id;

-- 2. Add templates to plan
INSERT INTO dna_app.customer_iso_plan_templates (plan_id, template_id)
SELECT 'plan-uuid'::UUID, t.id
FROM dna_app.templates t
WHERE t.id IN ('template-uuid-1'::UUID, 'template-uuid-2'::UUID);

-- 3. Generate tasks from template questions (application logic)
-- For each fillable_section in template.template_structure:
INSERT INTO dna_app.customer_tasks (
    customer_id,
    plan_id,
    task_type,
    task_scope,
    section_id,
    title,
    description,
    priority,
    requires_evidence,
    evidence_description,
    auto_generated,
    status
) VALUES (
    123,
    'plan-uuid'::UUID,
    'answer_question',
    'question',
    section.id,
    section.title,
    section.question_context,
    section.priority,
    section.requires_evidence,
    section.evidence_description,
    true,
    'pending'
);
```

### **Workflow 3: Customer Answers Question**

```sql
-- 1. Customer submits answer
INSERT INTO dna_app.task_resolutions (
    task_id, resolution_type, resolution_data, is_final, resolved_by
) VALUES (
    'task-uuid'::UUID,
    'answer_provided',
    '{"answer": "Acme Corporation", "question_placeholder": "company_name"}'::jsonb,
    true,
    123  -- customer user id
);

-- 2. Mark task completed
UPDATE dna_app.customer_tasks
SET status = 'completed', completed_at = NOW(), completed_by = 123
WHERE id = 'task-uuid'::UUID;

-- 3. Check progress (automatically updated by view)
SELECT progress_percentage FROM dna_app.v_customer_iso_progress
WHERE customer_id = 123 AND iso_standard_id = 'iso-uuid'::UUID;
```

### **Workflow 4: Admin Removes Template Mid-Work**

```sql
-- 1. Mark plan template as ignored
UPDATE dna_app.customer_iso_plan_templates
SET is_ignored = true, ignored_at = NOW(), ignored_by = 1,
    ignore_reason = 'Template no longer relevant'
WHERE plan_id = 'plan-uuid'::UUID
  AND template_id = 'template-uuid'::UUID;

-- 2. Mark all related tasks as ignored
UPDATE dna_app.customer_tasks
SET is_ignored = true, ignored_at = NOW(), ignored_by = 1,
    ignore_reason = 'Template removed from plan'
WHERE plan_id = 'plan-uuid'::UUID
  AND document_id IN (
      SELECT id FROM dna_app.customer_documents
      WHERE template_id = 'template-uuid'::UUID
  );

-- 3. Progress view automatically excludes ignored tasks
-- No additional updates needed!
```

---

## 💡 **Best Practices**

1. **Always use ignored status instead of DELETE** for audit trail
2. **Check NULL values** when querying customer_id (NULL = global default)
3. **Use JSONB operators** for efficient config_value queries
4. **Exclude ignored tasks** from active queries: `WHERE is_ignored = false OR is_ignored IS NULL`
5. **Use the progress view** instead of manual calculations
6. **Interpolate variables** in application layer, not database
7. **Track usage** of task templates (increment usage_count)
8. **Require approval** for evidence uploads, auto-complete for answers

---

## 🚀 **Ready for Phase 3B**

With this database foundation in place, you can now build:

- Customer management APIs
- Plan assignment and modification logic
- Task generation from templates
- Task resolution workflow
- Progress tracking endpoints
- Configuration management
- Email notification system

All with proper audit trails and ignored status tracking! ✅
