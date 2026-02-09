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
    UNIQUE(customer_id, iso_standard_id)  -- One plan per ISO per customer
);

CREATE INDEX idx_customer_iso_plans_customer ON dna_app.customer_iso_plans(customer_id);
CREATE INDEX idx_customer_iso_plans_iso ON dna_app.customer_iso_plans(iso_standard_id);
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
Customer-specific documents generated from templates.

```sql
CREATE TABLE dna_app.customer_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES dna_app.catalog_templates(id) ON DELETE RESTRICT,
    document_name VARCHAR(500) NOT NULL,
    document_type VARCHAR(100),  -- policy, procedure, form, manual
    status VARCHAR(50) DEFAULT 'draft',  -- draft, in_progress, review, approved, rejected
    content JSONB NOT NULL,  -- Document structure with filled sections
    -- Format: {
    --   "document_title": "...",
    --   "fixed_sections": [...],
    --   "fillable_sections": [{...filled content...}]
    -- }
    version INTEGER DEFAULT 1,
    completion_percentage INTEGER DEFAULT 0,  -- Auto-calculated
    assigned_to INTEGER REFERENCES dna_app.users(id),
    created_by INTEGER REFERENCES dna_app.users(id),
    updated_by INTEGER REFERENCES dna_app.users(id),
    reviewed_by INTEGER REFERENCES dna_app.users(id),
    approved_by INTEGER REFERENCES dna_app.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,
    due_date DATE
);

CREATE INDEX idx_customer_documents_customer ON dna_app.customer_documents(customer_id);
CREATE INDEX idx_customer_documents_plan ON dna_app.customer_documents(plan_id);
CREATE INDEX idx_customer_documents_status ON dna_app.customer_documents(status);
CREATE INDEX idx_customer_documents_assigned ON dna_app.customer_documents(assigned_to);
```

#### 4. `customer_document_tasks`
Tasks to complete for each document.

```sql
CREATE TABLE dna_app.customer_document_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,  -- fillable_section, evidence_required, review, custom
    section_id VARCHAR(255),  -- Reference to fillable section ID from template
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, blocked, completed, cancelled
    priority VARCHAR(50) DEFAULT 'medium',  -- low, medium, high, urgent
    assigned_to INTEGER REFERENCES dna_app.users(id),
    due_date DATE,
    completed_at TIMESTAMP,
    completed_by INTEGER REFERENCES dna_app.users(id),
    created_by INTEGER REFERENCES dna_app.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX idx_document_tasks_document ON dna_app.customer_document_tasks(document_id);
CREATE INDEX idx_document_tasks_status ON dna_app.customer_document_tasks(status);
CREATE INDEX idx_document_tasks_assigned ON dna_app.customer_document_tasks(assigned_to);
CREATE INDEX idx_document_tasks_due ON dna_app.customer_document_tasks(due_date);
```

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

### Views

#### `v_customer_iso_progress`
Calculate progress for each customer ISO plan.

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
    -- Document metrics
    COUNT(DISTINCT d.id) as total_documents,
    COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END) as approved_documents,
    COUNT(DISTINCT CASE WHEN d.status IN ('draft', 'in_progress') THEN d.id END) as in_progress_documents,
    -- Task metrics
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'pending' THEN t.id END) as pending_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'blocked' THEN t.id END) as blocked_tasks,
    -- Progress calculations
    ROUND(
        CASE WHEN COUNT(DISTINCT d.id) > 0
        THEN (COUNT(DISTINCT CASE WHEN d.status = 'approved' THEN d.id END)::NUMERIC / COUNT(DISTINCT d.id) * 100)
        ELSE 0 END, 2
    ) as document_completion_percentage,
    ROUND(
        CASE WHEN COUNT(DISTINCT t.id) > 0
        THEN (COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END)::NUMERIC / COUNT(DISTINCT t.id) * 100)
        ELSE 0 END, 2
    ) as task_completion_percentage,
    p.target_completion_date,
    p.started_at,
    p.created_at
FROM dna_app.customer_iso_plans p
INNER JOIN dna_app.customers c ON p.customer_id = c.id
INNER JOIN dna_app.iso_standards iso ON p.iso_standard_id = iso.id
LEFT JOIN dna_app.customer_documents d ON p.id = d.plan_id
LEFT JOIN dna_app.customer_document_tasks t ON d.id = t.document_id
GROUP BY p.id, p.customer_id, p.iso_standard_id, p.plan_name, p.plan_status,
         iso.code, iso.name, c.company_name, p.target_completion_date, p.started_at, p.created_at;
```

---

## API Endpoints

### Customer ISO Plans

```
POST   /api/v1/customers/{customer_id}/iso-plans
GET    /api/v1/customers/{customer_id}/iso-plans
GET    /api/v1/customers/{customer_id}/iso-plans/{plan_id}
PUT    /api/v1/customers/{customer_id}/iso-plans/{plan_id}
DELETE /api/v1/customers/{customer_id}/iso-plans/{plan_id}
POST   /api/v1/customers/{customer_id}/iso-plans/{plan_id}/templates  # Set template selection
GET    /api/v1/customers/{customer_id}/iso-plans/{plan_id}/progress
POST   /api/v1/customers/{customer_id}/iso-plans/{plan_id}/generate-documents
```

### Customer Documents

```
GET    /api/v1/customer-documents?plan_id={plan_id}&status={status}
GET    /api/v1/customer-documents/{document_id}
PUT    /api/v1/customer-documents/{document_id}
DELETE /api/v1/customer-documents/{document_id}
POST   /api/v1/customer-documents/{document_id}/submit-review
POST   /api/v1/customer-documents/{document_id}/approve
POST   /api/v1/customer-documents/{document_id}/reject
GET    /api/v1/customer-documents/{document_id}/history
```

### Document Tasks

```
GET    /api/v1/customer-documents/{document_id}/tasks
POST   /api/v1/customer-documents/{document_id}/tasks
GET    /api/v1/tasks/{task_id}
PUT    /api/v1/tasks/{task_id}
DELETE /api/v1/tasks/{task_id}
POST   /api/v1/tasks/{task_id}/complete
GET    /api/v1/tasks?assigned_to={user_id}&status={status}  # My tasks
```

---

## Business Logic

### 1. Create ISO Plan Flow

```
1. User selects customer + ISO standard
2. User chooses template selection mode:
   - "All templates" (default)
   - "Selective" → User picks specific templates
3. System creates customer_iso_plan record
4. If selective, creates customer_iso_plan_templates records
5. Auto-generate documents for all included templates
6. For each document, auto-generate tasks from fillable sections
```

### 2. Document Generation

When a plan is created or templates are selected:

```python
for each selected template:
    1. Create customer_document record
    2. Copy template structure to document.content
    3. Set status = 'draft'
    4. Calculate initial completion_percentage = 0
    5. For each fillable_section in template:
        - If section.is_mandatory = true:
          - Create task (type='fillable_section')
        - If section.type = 'evidence':
          - Create task (type='evidence_required')
```

### 3. Task Auto-Generation

```python
def generate_tasks_from_template(document, template):
    tasks = []
    for section in template.fillable_sections:
        if section.is_mandatory or section.mandatory_confidence > 0.7:
            task = {
                "task_type": "fillable_section",
                "section_id": section.id,
                "title": f"Complete: {section.title}",
                "description": section.placeholder or f"Fill in {section.type}",
                "priority": "high" if section.is_mandatory else "medium"
            }
            tasks.append(task)
    return tasks
```

### 4. Progress Calculation

```python
def calculate_document_progress(document):
    total_sections = len(document.content.fillable_sections)
    filled_sections = count_filled_sections(document.content)
    return (filled_sections / total_sections) * 100

def calculate_plan_progress(plan):
    documents = get_plan_documents(plan)
    approved_docs = count_approved_documents(documents)
    total_docs = len(documents)
    return (approved_docs / total_docs) * 100
```

---

## Frontend UI Components

### 1. Customer ISO Plans Tab (in Customer Management)
- List of customer's ISO plans
- Add new ISO plan button
- For each plan:
  - ISO code/name
  - Progress bar
  - Document count
  - Task count
  - Target completion date
  - Actions: View, Edit, Delete

### 2. Create ISO Plan Modal
- Select ISO standard
- Template selection mode radio:
  - ○ All templates (default)
  - ○ Select specific templates
- If selective mode:
  - Checklist of available templates for that ISO
- Target completion date picker
- Plan name (optional)

### 3. ISO Plan Detail View
- Overview card: ISO info, progress, dates
- Tabs:
  - **Documents**: List of all documents with status
  - **Tasks**: Kanban board or list of tasks
  - **Progress**: Visual dashboard
  - **Timeline**: Activity feed

### 4. Document Editor
- Split view: Template structure + Content editor
- For each fillable section:
  - Show placeholder/guidance
  - Input field (text, table, etc.)
  - Mark as complete checkbox
  - Related tasks indicator
- Submit for review button
- Save draft button

### 5. Task Board
- Columns: Pending / In Progress / Blocked / Completed
- Drag-and-drop between columns
- Filter by:
  - Document
  - Assigned user
  - Priority
  - Due date
- Create custom task button

### 6. Progress Dashboard
- Overall plan completion (pie chart)
- Document status breakdown (bar chart)
- Task completion trend (line chart)
- Upcoming deadlines (list)
- Recent activity (timeline)

---

## Implementation Phases

### Phase 1: Database & Core API (Week 1-2)
- [ ] Create database migration
- [ ] Create backend models
- [ ] Implement ISO Plans API
- [ ] Implement document generation logic
- [ ] Implement task auto-generation

### Phase 2: Document Management (Week 3-4)
- [ ] Customer Documents API
- [ ] Document editor frontend
- [ ] Document status workflow
- [ ] Document history/versioning

### Phase 3: Task Management (Week 5)
- [ ] Document Tasks API
- [ ] Task board UI
- [ ] Task assignment and notifications
- [ ] Task filtering and search

### Phase 4: Progress & Reporting (Week 6)
- [ ] Progress calculation views
- [ ] Progress dashboard UI
- [ ] Reports and exports
- [ ] Analytics

### Phase 5: Polish & Integration (Week 7-8)
- [ ] Customer ISO Plans UI in admin
- [ ] Integrate with existing customer page
- [ ] Notifications and reminders
- [ ] Testing and bug fixes

---

## Key Decisions

### 1. Template Selection Modes
**Decision:** Support both "all" and "selective" modes
- Most customers will use "all" (simpler)
- Advanced users can cherry-pick templates

### 2. Task Auto-Generation
**Decision:** Auto-generate tasks from mandatory fillable sections
- Users can add custom tasks
- Task completion doesn't block document submission

### 3. Document Versioning
**Decision:** Simple version incrementing on each save
- Keep history in separate table
- Can restore previous versions

### 4. Progress Calculation
**Decision:** Two-level progress
- Document level: % of fillable sections completed
- Plan level: % of documents approved

### 5. Multi-User Collaboration
**Decision:** Basic assignment for MVP
- Assign documents to users
- Assign tasks to users
- Track who created/updated/approved

---

## Sample User Scenarios

### Scenario 1: New ISO 27001 Project
```
1. Admin creates customer "Acme Corp"
2. Admin assigns ISO 27001 with "All templates"
3. System generates 15 documents from 15 templates
4. System creates 120 tasks (8 tasks per document average)
5. Admin assigns documents to team members
6. Team members fill documents and complete tasks
7. Manager reviews and approves documents
8. Progress dashboard shows 67% complete
```

### Scenario 2: Selective Template Assignment
```
1. Admin assigns ISO 9001 to customer
2. Chooses "Selective" mode
3. Selects only 5 out of 10 templates (customer doesn't need all)
4. System generates only 5 documents
5. Reduces scope for smaller projects
```

### Scenario 3: Task Management
```
1. User opens document "Quality Policy"
2. Sees 3 auto-generated tasks:
   - Complete: Quality Objectives section
   - Provide evidence: Management Review records
   - Complete: Improvement Actions table
3. User completes 2 tasks
4. User adds custom task: "Get approval from CEO"
5. Document shows 75% task completion
```

---

## Questions to Clarify

1. **User Roles:** Do we need separate roles for:
   - Admin (can create plans)
   - Manager (can approve documents)
   - Team Member (can edit documents)
   - Viewer (read-only)

2. **Notifications:** Should we send notifications for:
   - Document assigned
   - Task assigned
   - Document submitted for review
   - Document approved/rejected
   - Deadline approaching

3. **Document Templates:** When customer document is generated:
   - Copy the template structure as-is?
   - Allow customer to customize template before generating documents?

4. **Multiple ISO Plans:** Can customer have multiple ACTIVE plans for same ISO?
   - Example: ISO 27001 (2023 project - completed)
   - Example: ISO 27001 (2026 renewal - active)

5. **Evidence Management:** Should we add file attachments to:
   - Documents (supporting evidence)
   - Tasks (proof of completion)

6. **Integration with existing `documents` table:**
   - Keep separate or merge?
   - Current `documents` table seems to be for different purpose

---

## Next Steps

**Please review this plan and let me know:**

1. Does this architecture match your vision?
2. Any missing features or requirements?
3. Should I proceed with Phase 1 implementation?
4. Any changes to the database schema?
5. Answers to the clarification questions above?

Once approved, I'll start with the database migration and core API implementation.
