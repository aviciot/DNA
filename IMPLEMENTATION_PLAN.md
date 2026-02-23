# DNA Document Generation - Complete Implementation Plan

## Overview
Transform templates with placeholders → Interview tasks → Final documents

## Database Structure (Current State)

```sql
iso_standards (id, code, name)
    ↓ many-to-many ↓
template_iso_standards (template_id, iso_standard_id) ✅ DONE
    ↓ many-to-many ↓
templates (id, name, template_structure JSONB) ✅ DONE
    ↑
    Contains: fillable_sections with questions

customers (id, name, contact_info)
    ↓ assignment ↓
customer_templates (customer_id, template_id) 🔨 NEED
    OR
customer_iso_plans (customer_id, iso_standard_id) ✅ EXISTS

documents (customer_id, template_id, status) 🔨 NEED
    ↓ has many ↓
document_answers (document_id, question_id, answer) 🔨 NEED
```

## Phase 2: Template-ISO Association

### Backend API Endpoints

```python
# 1. Associate template with ISO standards
POST /api/v1/templates/{template_id}/iso-standards
{
  "iso_standard_ids": ["uuid1", "uuid2"]
}

# 2. Get templates by ISO
GET /api/v1/iso-standards/{iso_id}/templates
Response: [list of templates]

# 3. Get ISO standards for template
GET /api/v1/templates/{template_id}/iso-standards
Response: [list of ISO standards]

# 4. Update template-ISO associations
PUT /api/v1/templates/{template_id}/iso-standards
{
  "iso_standard_ids": ["uuid1", "uuid2"]
}
```

### UI Components

```typescript
// Template Studio - Add ISO selection
<TemplateISOSelector
  templateId={template.id}
  selectedISOIds={template.iso_standards}
  onChange={(isoIds) => updateTemplateISOs(isoIds)}
/>

// ISO Standards Page - Show templates
<ISOStandardCard
  standard={iso}
  templatesCount={iso.templates_count}
  onClick={() => navigate(`/iso/${iso.id}/templates`)}
/>
```

## Phase 3: Customer Assignment

### Tables Needed

```sql
-- Option A: Assign entire ISO (customer gets all templates)
customer_iso_plans (already exists) ✅

-- Option B: Assign specific templates
CREATE TABLE customer_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
  assigned_at TIMESTAMP DEFAULT NOW(),
  assigned_by INTEGER REFERENCES auth.users(id),
  status VARCHAR(50) DEFAULT 'active',
  due_date TIMESTAMP,
  UNIQUE(customer_id, template_id)
);
```

### Backend API Endpoints

```python
# 1. Assign ISO to customer (gets all templates)
POST /api/v1/customers/{customer_id}/iso-standards
{
  "iso_standard_ids": ["uuid1"]
}

# 2. Assign specific templates to customer
POST /api/v1/customers/{customer_id}/templates
{
  "template_ids": ["uuid1", "uuid2"],
  "due_date": "2024-03-01"
}

# 3. Get customer's assigned templates (from ISO + specific)
GET /api/v1/customers/{customer_id}/assigned-templates
Response: [
  {
    "template": {...},
    "source": "iso_standard" | "direct_assignment",
    "iso_standard": {...} (if from ISO),
    "due_date": "..."
  }
]
```

### UI Components

```typescript
// Customer Detail Page
<CustomerTemplateAssignment
  customer={customer}
  assignedISOs={customer.iso_standards}
  assignedTemplates={customer.templates}
  onAssignISO={(isoId) => assignISOToCustomer(isoId)}
  onAssignTemplate={(templateId) => assignTemplateToCustomer(templateId)}
/>
```

## Phase 4: Document Generation & Interview

### Tables Needed

```sql
-- Generated documents
CREATE TABLE generated_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers(id),
  template_id UUID NOT NULL REFERENCES templates(id),
  title VARCHAR(255),
  status VARCHAR(50) DEFAULT 'draft',
  -- draft, in_progress, completed, approved
  document_path TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by INTEGER REFERENCES auth.users(id),
  completed_at TIMESTAMP,
  approved_at TIMESTAMP,
  approved_by INTEGER REFERENCES auth.users(id)
);

-- Customer answers to questions
CREATE TABLE document_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES generated_documents(id) ON DELETE CASCADE,
  question_id VARCHAR(100), -- e.g., "ciso_name"
  question_text TEXT,
  answer TEXT,
  answered_at TIMESTAMP DEFAULT NOW(),
  answered_by INTEGER REFERENCES auth.users(id)
);

-- Interview tasks (one per question)
CREATE TABLE interview_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES generated_documents(id) ON DELETE CASCADE,
  question_id VARCHAR(100),
  question_text TEXT,
  question_hint TEXT,
  field_type VARCHAR(50),
  is_mandatory BOOLEAN DEFAULT true,
  status VARCHAR(50) DEFAULT 'pending',
  -- pending, in_progress, completed, skipped
  assigned_to INTEGER REFERENCES auth.users(id),
  completed_at TIMESTAMP,
  display_order INTEGER
);
```

### Backend API Endpoints

```python
# 1. Start document generation
POST /api/v1/customers/{customer_id}/documents/generate
{
  "template_id": "uuid",
  "title": "Business Continuity Plan 2024"
}
Response: {
  "document_id": "uuid",
  "interview_tasks": [
    {
      "id": "uuid",
      "question": "Who is your CISO?",
      "field_type": "text",
      "is_mandatory": true
    }
  ]
}

# 2. Get interview tasks
GET /api/v1/documents/{document_id}/interview-tasks
Response: [list of tasks with status]

# 3. Submit answer
POST /api/v1/documents/{document_id}/answers
{
  "question_id": "ciso_name",
  "answer": "John Smith"
}

# 4. Complete interview & generate final document
POST /api/v1/documents/{document_id}/finalize
→ Replaces all placeholders with answers
→ Generates final PDF
Response: {
  "document_url": "/downloads/documents/uuid.pdf",
  "missing_mandatory": [] // or list of unanswered
}
```

### UI Flow

```typescript
// 1. Customer Dashboard - Shows assigned templates
<AssignedTemplates
  templates={customer.assignedTemplates}
  onStartDocument={(template) => startDocumentGeneration(template)}
/>

// 2. Interview Flow - Question by question
<InterviewWizard
  document={document}
  tasks={interviewTasks}
  onAnswer={(questionId, answer) => submitAnswer(questionId, answer)}
  onComplete={() => finalizeDocument()}
/>

// 3. Document Preview - Show progress
<DocumentProgress
  document={document}
  answeredCount={10}
  totalCount={18}
  mandatoryRemaining={3}
/>

// 4. Final Document - Download
<FinalDocument
  document={document}
  downloadUrl={document.document_url}
/>
```

## Implementation Order

1. ✅ Phase 1: Template Creation (DONE)
2. 🔨 Phase 2: Template-ISO Association (START HERE)
   - Create API endpoints
   - Update Template Studio UI
   - Add ISO filter/view
3. 🔨 Phase 3: Customer Assignment
   - Create customer_templates table
   - Create assignment APIs
   - Update Customer UI
4. 🔨 Phase 4: Document Generation
   - Create tables
   - Create generation APIs
   - Build interview wizard UI
   - Implement PDF generation with filled placeholders

## Testing Strategy

### E2E Test Flow

```python
def test_complete_flow():
    # Phase 1: Template Creation
    template = create_template_from_analysis()
    assert template.status == 'active'
    assert len(template.fillable_sections) > 0

    # Phase 2: Associate with ISO
    associate_template_with_iso(template.id, iso_27001.id)
    templates = get_iso_templates(iso_27001.id)
    assert template.id in [t.id for t in templates]

    # Phase 3: Assign to Customer
    assign_iso_to_customer(customer.id, iso_27001.id)
    assigned = get_customer_assigned_templates(customer.id)
    assert template.id in [t.id for t in assigned]

    # Phase 4: Generate Document
    doc = start_document_generation(customer.id, template.id)
    tasks = get_interview_tasks(doc.id)
    assert len(tasks) == len(template.fillable_sections)

    # Answer questions
    for task in tasks:
        submit_answer(doc.id, task.question_id, "Test Answer")

    # Finalize
    final_doc = finalize_document(doc.id)
    assert final_doc.status == 'completed'
    assert final_doc.document_url exists

    # Verify PDF has answers (not placeholders)
    pdf_content = read_pdf(final_doc.document_url)
    assert "{{ciso_name}}" not in pdf_content
    assert "Test Answer" in pdf_content
```

## Next Steps

**Starting with Phase 2 now...**
