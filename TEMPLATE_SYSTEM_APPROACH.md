# Template System - Interview-Driven Document Generation

## Overview

This document describes the approach for the DNA template system that enables efficient, interview-driven document generation for ISO certification.

---

## Core Concept

**One Interview → Multiple Documents**

Users answer questions once, and the system intelligently populates all relevant documents across different contexts.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    TEMPLATE STORAGE                         │
│  - DOCX files with {{placeholders}}                         │
│  - JSON metadata (field definitions)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 PLACEHOLDER DETECTION                        │
│  - Parse DOCX to find {{field_name}} patterns              │
│  - Extract field metadata (type, required, context)         │
│  - Support both AI detection and explicit markup            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              CROSS-DOCUMENT AGGREGATION                      │
│  - Collect fields from multiple templates                   │
│  - Deduplicate by semantic similarity                       │
│  - Calculate usage count and priority                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 INTERVIEW GENERATION                         │
│  - Build questionnaire from aggregated fields               │
│  - Prioritize by: mandatory > usage count > type            │
│  - Show "will populate X documents" per question            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   DATA COLLECTION                            │
│  - User answers interview questions                         │
│  - Store in customer profile (central storage)              │
│  - One answer can populate multiple document fields         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              SMART DOCUMENT GENERATION                       │
│  - Load template DOCX                                       │
│  - Map customer data to placeholders                        │
│  - AI generates context-appropriate text                    │
│  - Replace placeholders with generated content              │
│  - Convert to PDF                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Storage Format

**Templates: DOCX + JSON**
- **DOCX File**: Contains actual document with formatting, tables, images, and {{placeholders}}
- **JSON Metadata**: Describes fields (type, label, required, hints, semantic tags)

**Why both?**
- DOCX preserves formatting perfectly (for generation)
- JSON enables smart form building (for data collection)

**Customer Data: JSON**
- Simple key-value storage
- One piece of data used across multiple documents
- Easy to query and update

### 2. Placeholder Format

**Explicit Markup (Preferred):**
```
{{company_name}}
{{effective_date|date}}
{{logo|image|required}}
{{backup_solution|textarea|required|evidence:backup_logs}}
```

**Syntax:**
```
{{field_name|type|required|evidence:filename}}
```

**AI Auto-Detection (Fallback):**
- Analyze example documents
- Detect variable content patterns
- Suggest placeholders for user confirmation

### 3. Semantic Mapping

**Same data, different contexts:**

```json
{
  "backup_solution": {
    "value": "AWS S3 for daily backups",
    "maps_to": [
      {
        "document": "Backup Strategy",
        "placeholder": "{{backup_solution_description}}",
        "context": "policy_document",
        "prompt": "Describe professionally in 2-3 sentences"
      },
      {
        "document": "Risk Assessment",
        "placeholder": "{{third_party_dependencies}}",
        "context": "risk_listing",
        "prompt": "Format as risk dependency with impact level"
      },
      {
        "document": "Cloud Services",
        "placeholder": "{{cloud_providers}}",
        "context": "inventory_table",
        "prompt": "Format as table row"
      }
    ]
  }
}
```

**AI generates different text for each context automatically.**

### 4. Incremental Question Building

Questions are built **on-demand**, not upfront:

```
User Flow:
1. Select templates (by ISO standard or individual selection)
2. System aggregates only selected templates
3. Build questionnaire from aggregated fields
4. User can add more templates later
5. System re-aggregates and shows new questions
```

**Deduplication:**
- If 5 documents need "logo", ask once
- If 10 documents need "company_name", ask once
- Show usage count: "This will populate 10 documents"

---

## Preview System

**Critical for validation:**

### Three Preview Types

1. **Template Preview** - Admin sees structure + sample data
2. **Fill Preview** - Real-time preview as user fills form
3. **Final Preview** - PDF viewer before export

### Preview Pipeline

```
Template DOCX + Sample/Real Data
         ↓
  Merge placeholders
         ↓
   Generate DOCX
         ↓
   Convert to PDF
         ↓
  Display in browser
```

---

## Database Schema

### Templates
```sql
CREATE TABLE templates (
  id UUID PRIMARY KEY,
  name VARCHAR(255),
  description TEXT,
  template_file_path VARCHAR(500),  -- Path to DOCX
  template_metadata JSONB,          -- Field definitions
  iso_standard_id UUID,
  version_number INT,
  status VARCHAR(50),  -- draft, approved, archived
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Template Metadata Structure
```json
{
  "fields": [
    {
      "placeholder": "{{company_name}}",
      "label": "Company Legal Name",
      "type": "text",
      "required": true,
      "hint": "Enter full registered company name",
      "semantic_tags": ["organization", "company", "legal"],
      "locations": [
        {"paragraph": 1, "position": 10},
        {"table": 1, "row": 2, "col": 1}
      ]
    },
    {
      "placeholder": "{{logo}}",
      "label": "Company Logo",
      "type": "image",
      "required": true,
      "evidence": true,
      "hint": "PNG or JPG, minimum 300x300 pixels",
      "semantic_tags": ["branding", "image"],
      "locations": [{"paragraph": 0}]
    }
  ]
}
```

### Customer Data
```sql
CREATE TABLE customer_profiles (
  customer_id UUID PRIMARY KEY,
  profile_data JSONB,  -- All customer information
  updated_at TIMESTAMP
);
```

### Customer Profile Structure
```json
{
  "basic_info": {
    "company_name": "Acme Corporation",
    "industry": "SaaS",
    "employee_count": 75
  },
  "contacts": {
    "ciso_name": "John Smith",
    "ciso_email": "john@acme.com"
  },
  "infrastructure": {
    "backup_solution": {
      "provider": "AWS",
      "service": "S3",
      "purpose": "daily backups only",
      "raw_answer": "We use AWS S3 for daily backups"
    }
  },
  "evidence": {
    "logo": "/storage/customers/acme/logo.png",
    "backup_logs": "/storage/customers/acme/backup_logs.pdf"
  }
}
```

---

## Implementation Phases

### Phase 1: Proof of Concept (Current)
**Goal:** Validate template → preview pipeline works

**Deliverables:**
1. Manual template upload (DOCX with {{placeholders}})
2. Placeholder parser
3. Simple form generation
4. Document generator (merge + PDF)
5. Preview display
6. Basic API endpoints
7. Simple frontend test page

**Success Criteria:**
- Upload template → See fields → Fill form → Generate PDF → View preview

---

### Phase 2: Full Template Management
**Goal:** Complete template system with AI assistance

**Deliverables:**
1. AI auto-detection for example documents
2. Template editor (adjust field metadata)
3. Template versioning
4. Approval workflow
5. ISO standard mapping

---

### Phase 3: Interview System
**Goal:** Multi-template questionnaire builder

**Deliverables:**
1. Field aggregation across templates
2. Deduplication algorithm
3. Priority calculation
4. Interview question generator
5. Progress tracking

---

### Phase 4: Smart Generation
**Goal:** Context-aware AI content generation

**Deliverables:**
1. Semantic mapping system
2. AI content generation per context
3. Consistency checking
4. Bulk document generation

---

## Guidelines for Template Creation

### Option 1: Explicit Template (Recommended)

**Create template with placeholders:**
```
Company: {{company_name}}
Logo: {{logo|image|required}}
Date: {{effective_date|date}}
Description: {{backup_solution|textarea|required|evidence:backup_logs}}
```

**Best for:**
- New templates from scratch
- Maximum control
- Highest accuracy

### Option 2: Example Document

**Upload real document:**
```
Company: Acme Corporation
Logo: [Acme Logo]
Date: January 15, 2026
```

**AI detects variables and suggests placeholders**

**Best for:**
- Existing completed documents
- Quick conversion
- Legacy document migration

---

## Technical Stack

### Backend
- **Python**: Core logic
- **python-docx**: DOCX manipulation
- **docx2pdf** or **pypandoc**: PDF conversion
- **Claude API**: AI analysis and generation
- **FastAPI**: API endpoints
- **PostgreSQL**: Data storage

### Frontend
- **Next.js 14**: UI framework
- **React**: Components
- **react-pdf** or **pdf.js**: PDF viewer
- **TailwindCSS**: Styling

---

## Success Metrics

1. **Efficiency**: One interview fills 10+ documents
2. **Accuracy**: 95%+ field detection confidence
3. **Consistency**: Same data appears correctly across all documents
4. **Speed**: Generate 10 documents in < 30 seconds
5. **Quality**: Preview matches final output 100%

---

## Current Status

- ✅ Requirements defined
- ✅ Architecture designed
- 🔄 **Phase 1 in progress** (Proof of Concept)
- ⏳ Phase 2-4 pending

---

## Next Steps

See `PHASE_1_IMPLEMENTATION.md` for current implementation details.
