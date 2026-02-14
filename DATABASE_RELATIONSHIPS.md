# DNA System - Database Relationships Diagram

## Overview: Customer → ISO Plan → Templates → Tasks

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CUSTOMER WORKSPACE FLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

        ┌─────────────────┐
        │   CUSTOMERS     │
        │─────────────────│
        │ • id (PK)       │
        │ • name          │
        │ • email         │
        │ • phone         │
        └────────┬────────┘
                 │
                 │ 1:N
                 ▼
        ┌──────────────────────┐
        │ CUSTOMER_ISO_PLANS   │◄────────────────┐
        │──────────────────────│                 │
        │ • id (PK)            │                 │
        │ • customer_id (FK)   │                 │
        │ • iso_standard_id(FK)│                 │
        │ • plan_status        │                 │
        │ • target_date        │                 │
        └──────────┬───────────┘                 │
                   │                             │
                   │ N:M                         │
                   │ (via plan_templates)        │
                   ▼                             │
        ┌────────────────────────────────┐       │
        │ CUSTOMER_ISO_PLAN_TEMPLATES    │       │
        │────────────────────────────────│       │
        │ • id (PK)                      │       │
        │ • plan_id (FK) ────────────────┘       │
        │ • template_id (FK) ──────┐             │
        │ • included               │             │
        │ • is_ignored             │             │
        └──────────────────────────┘             │
                                   │             │
                                   │ N:1         │
                                   ▼             │
        ┌─────────────────────────────────┐      │
        │         TEMPLATES               │      │
        │─────────────────────────────────│      │
        │ • id (PK)                       │      │
        │ • name                          │      │
        │ • description                   │      │
        │ • iso_standard                  │      │
        │ • template_file_id (FK) ────┐   │      │
        │ • template_structure (JSONB)│   │      │
        │ • total_fillable_sections   │   │      │
        │ • status                    │   │      │
        └─────────────────────────────┘   │      │
                                          │      │
                                   N:1    │      │
                                          ▼      │
        ┌─────────────────────────────────────┐  │
        │      TEMPLATE_FILES                 │  │
        │     (Reference Documents)           │  │
        │─────────────────────────────────────│  │
        │ • id (PK)                           │  │
        │ • filename                          │  │
        │ • original_filename                 │  │
        │   "ISMS 20 Patch management.docx"   │  │
        │ • file_path                         │  │
        │ • iso_standard_id (FK)              │  │
        │ • file_type (reference/template)    │  │
        │ • uploaded_at                       │  │
        └─────────────────────────────────────┘  │
                                                 │
        ┌────────────────────────────────────────┘
        │
        │ 1:N (Tasks generated from plan)
        ▼
┌──────────────────────────────┐
│     CUSTOMER_TASKS           │
│──────────────────────────────│
│ • id (PK)                    │
│ • customer_id (FK)           │
│ • plan_id (FK) ──────────────┘  ← Links to plan, NOT to specific template!
│ • document_id (FK) [NULL]    │  ⚠️ Usually NULL (no documents created yet)
│ • task_type                  │
│ • title                      │
│ • status                     │
│ • priority                   │
│ • requires_evidence          │
│ • due_date                   │
└──────────────────────────────┘
        │
        │ N:1 (IF document created)
        ▼
┌──────────────────────────────────┐
│   CUSTOMER_DOCUMENTS             │  ⚠️ TABLE EXISTS BUT EMPTY!
│──────────────────────────────────│     (Documents created when user
│ • id (PK)                        │      fills out templates)
│ • customer_id (FK)               │
│ • plan_id (FK)                   │
│ • template_id (FK)               │
│ • template_name                  │
│ • document_name                  │
│ • status                         │
│ • completion_percentage          │
│ • content (JSONB)                │  ← Filled template content
└──────────────────────────────────┘
```

---

## Current Data Flow (What Actually Happens)

```
┌──────────────┐
│   ADMIN      │
└──────┬───────┘
       │
       │ 1. Creates ISO Plan for Customer
       ▼
┌────────────────────────┐
│  Customer ISO Plan     │  Example: "ISO 27001:2022" for "test1"
│  (Active)              │
└────────┬───────────────┘
         │
         │ 2. Assigns Templates to Plan
         ▼
┌─────────────────────────────────────┐
│  Plan-Template Assignment           │
│  ✅ "ISMS 20 Patch management"      │  ← Links template to plan
└────────┬────────────────────────────┘
         │
         │ 3. System Generates Tasks
         ▼
┌──────────────────────────────────────┐
│  Tasks Created                       │
│  • Question 1: "What is org name?"   │
│  • Question 2: "Who manages patches?"│  ← All have plan_id
│  • Question 3: "Scan frequency?"     │  ← All have document_id = NULL
│  • ...                               │
└──────────────────────────────────────┘
         │
         │ 4. Regular User Works on Tasks
         ▼
┌──────────────────────────────────────┐
│  User Completes Tasks                │
│  (Answers questions, uploads docs)   │
└──────────────────────────────────────┘
         │
         │ 5. (FUTURE) Document Generated
         ▼
┌──────────────────────────────────────┐
│  Customer Document Created           │  ⚠️ NOT IMPLEMENTED YET
│  (Filled template saved as document) │
└──────────────────────────────────────┘
```

---

## The Gap / Missing Link

### ❌ Problem: Tasks Don't Link to Specific Templates

```
Current Schema:
customer_tasks
├─ plan_id ✅      (knows which ISO plan)
├─ document_id ⚠️   (always NULL - no documents)
└─ template_id ❌   (MISSING - can't tell which template created this task!)

Result:
- All tasks for a plan are shown under ALL templates
- Can't distinguish which task came from which template
```

### Example Data:

**Customer: test1**
```
ISO 27001:2022 Plan
└─ Template: "ISMS 20 Patch management"
    └─ 4 Tasks (but tasks only know plan_id, not template_id!)
       • "What is org name?"
       • "Who manages patches?"
       • "What is scan frequency?"
       • "Risk assessment process?"
```

---

## Key Relationships Summary

| From | To | Relationship | Foreign Key | Purpose |
|------|-----|--------------|-------------|---------|
| customers | customer_iso_plans | 1:N | customer_id | One customer, many ISO plans |
| customer_iso_plans | customer_iso_plan_templates | 1:N | plan_id | One plan, many templates |
| templates | customer_iso_plan_templates | 1:N | template_id | One template used by many plans |
| templates | template_files | N:1 | template_file_id | Templates created from reference docs |
| customer_iso_plans | customer_tasks | 1:N | plan_id | Plan generates tasks |
| customer_documents | customer_tasks | 1:N | document_id | Document can have tasks (NOT USED) |

---

## What We Show in UI

```
Frontend Display:
┌─────────────────────────────────────────┐
│  Customer: test1                        │
│  ┌───────────────────────────────────┐  │
│  │ ISO 27001:2022                    │  │  ← From: customer_iso_plans
│  │                                   │  │
│  │  📄 ISMS 20 Patch management      │  │  ← From: customer_iso_plan_templates
│  │     4 Tasks • 0 completed  [▼]    │  │     + templates
│  │                                   │  │
│  │     └─ Tasks when expanded:       │  │  ← From: customer_tasks
│  │        • Question 1               │  │     WHERE plan_id = plan.id
│  │        • Question 2               │  │
│  │        • Question 3               │  │
│  │        • Question 4               │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘

API Call:
GET /api/v1/customers/5/plan-templates
Returns templates with task counts per plan
```

---

## Future Enhancement Needed

To properly link tasks to specific templates:

```sql
-- Option 1: Add template_id to tasks
ALTER TABLE customer_tasks
ADD COLUMN template_id UUID REFERENCES templates(id);

-- Option 2: Create task-template junction table
CREATE TABLE task_template_mapping (
    task_id UUID REFERENCES customer_tasks(id),
    template_id UUID REFERENCES templates(id),
    PRIMARY KEY (task_id, template_id)
);
```

This would allow:
- Each task knows which template generated it
- Accurate task counts per template
- Better organization in UI
