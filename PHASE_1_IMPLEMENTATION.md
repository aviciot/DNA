# Phase 1: Template Preview System - Proof of Concept

## Goal

Validate that the template → fill → preview → PDF pipeline works end-to-end with real formatting preservation.

## Success Criteria

✅ User can upload a DOCX template with `{{placeholders}}`
✅ System detects all placeholders automatically
✅ User can fill a form with test data
✅ System generates filled DOCX with correct data
✅ System converts to PDF preserving formatting
✅ User can preview PDF in browser

**If all above work → Approach is validated ✅**

---

## Deliverables

### 1. Backend Services

#### `simple_placeholder_parser.py`
- Parse DOCX files
- Find all `{{placeholder}}` patterns
- Extract field metadata
- Return structured field list

#### `simple_document_generator.py`
- Load template DOCX
- Replace placeholders with data
- Handle text, dates, images
- Save filled DOCX
- Convert to PDF

#### API Endpoints (`/api/v1/template-preview`)
- `POST /upload-template` - Upload and parse
- `POST /generate-preview` - Generate filled PDF
- `GET /download/{template_id}` - Download PDF

### 2. Frontend

#### Test Page (`/template-preview`)
- Upload template file
- Show detected fields
- Form to fill data
- Generate preview button
- PDF viewer (iframe or react-pdf)

### 3. Dependencies

**Backend:**
```txt
python-docx==1.1.0      # DOCX manipulation
docx2pdf==0.1.8         # PDF conversion (Windows)
pypandoc==1.11          # Alternative PDF conversion (cross-platform)
```

**Frontend:**
```json
{
  "react-pdf": "^7.5.1",  // PDF viewer
  "@react-pdf/renderer": "^3.1.14"  // Alternative
}
```

---

## Implementation Tasks

### Task 1: Backend - Placeholder Parser ⭐ START HERE

**File:** `dashboard/backend/app/services/simple_placeholder_parser.py`

**Function 1: Extract placeholders from DOCX**
```python
def extract_placeholders_from_docx(docx_path: str) -> Dict:
    """
    Find all {{placeholder}} patterns in DOCX

    Returns:
    {
        "template_path": str,
        "fields": [
            {
                "name": str,           # e.g., "company_name"
                "label": str,          # e.g., "Company Name"
                "type": str,           # text, date, image, etc.
                "required": bool,
                "locations": [...]     # Where found in document
            }
        ]
    }
    """
```

**Features:**
- Scan paragraphs for `{{...}}` patterns
- Scan tables for `{{...}}` patterns
- Scan headers/footers
- Detect type from name (e.g., "date" in name → date type)
- Track locations for debugging

**Time Estimate:** 3 hours

---

### Task 2: Backend - Document Generator

**File:** `dashboard/backend/app/services/simple_document_generator.py`

**Function: Generate filled document**
```python
def generate_filled_document(
    template_path: str,
    filled_data: Dict[str, Any],
    output_dir: str
) -> Dict:
    """
    Generate filled document from template

    Args:
        template_path: Path to template DOCX
        filled_data: Dict of placeholder -> value
        output_dir: Where to save output

    Returns:
        {
            "docx_path": str,
            "pdf_path": str,
            "success": bool
        }
    """
```

**Features:**
- Load template DOCX
- Replace text placeholders
- Insert images for image placeholders
- Format dates properly
- Save filled DOCX
- Convert to PDF
- Handle errors gracefully

**Time Estimate:** 4 hours

---

### Task 3: Backend - API Endpoints

**File:** `dashboard/backend/app/routes/template_preview.py`

**Endpoints:**

1. **Upload Template**
```python
@router.post("/upload-template")
async def upload_template(file: UploadFile):
    """
    Upload template and extract fields

    Returns:
    {
        "template_id": str,
        "filename": str,
        "fields": [...]
    }
    """
```

2. **Generate Preview**
```python
@router.post("/generate-preview")
async def generate_preview(
    template_id: str,
    filled_data: Dict[str, Any]
):
    """
    Generate preview PDF

    Returns:
    {
        "preview_id": str,
        "pdf_url": str,
        "success": bool
    }
    """
```

3. **Download PDF**
```python
@router.get("/download/{preview_id}")
async def download_preview(preview_id: str):
    """
    Stream PDF file
    """
    return FileResponse(pdf_path, media_type="application/pdf")
```

**Time Estimate:** 2 hours

---

### Task 4: Frontend - Upload & Form UI

**File:** `dashboard/frontend/src/app/template-preview/page.tsx`

**Components:**

1. **Upload Section**
```tsx
<div>
  <h2>Step 1: Upload Template</h2>
  <input type="file" accept=".docx" onChange={handleUpload} />
</div>
```

2. **Form Section** (Dynamic based on detected fields)
```tsx
<div>
  <h2>Step 2: Fill Data</h2>
  {fields.map(field => (
    <FormField
      key={field.name}
      field={field}
      onChange={handleChange}
    />
  ))}
  <button onClick={handleGenerate}>Generate Preview</button>
</div>
```

3. **Preview Section**
```tsx
<div>
  <h2>Step 3: Preview</h2>
  <iframe src={pdfUrl} />
  {/* OR */}
  <PDFViewer file={pdfUrl} />
</div>
```

**Time Estimate:** 3 hours

---

### Task 5: Test Template Creation

**File:** `DNA/test_templates/Test_Policy_Template.docx`

**Content:**
```
[Logo Area]
{{logo|image|required}}

INFORMATION SECURITY POLICY

Company: {{company_name}}
Effective Date: {{effective_date|date}}
Policy Owner: {{ciso_name}}

1. Purpose
This policy establishes the information security framework
for {{company_name}}.

2. Scope
This policy applies to all employees of {{company_name}}.

3. Backup Solution
{{backup_solution|textarea}}

4. Responsibilities
The CISO ({{ciso_name}}) is responsible for maintaining
this policy and ensuring compliance.

[Table]
┌──────────────┬──────────────┐
│ Role         │ Owner        │
├──────────────┼──────────────┤
│ CISO         │ {{ciso_name}}│
│ Company      │ {{company_name}}│
└──────────────┴──────────────┘
```

**Time Estimate:** 30 minutes

---

### Task 6: Integration Testing

**Test Cases:**

1. **Upload template** → Verify fields detected correctly
2. **Fill simple text** → Verify replacement works
3. **Fill date field** → Verify formatting correct
4. **Upload image** → Verify image inserted
5. **Generate PDF** → Verify formatting preserved
6. **Preview display** → Verify PDF shows correctly

**Test Data:**
```json
{
  "company_name": "Acme Corporation",
  "effective_date": "2026-02-11",
  "ciso_name": "John Smith",
  "backup_solution": "We use AWS S3 for daily automated backups with 30-day retention.",
  "logo": "/path/to/test_logo.png"
}
```

**Time Estimate:** 2 hours

---

## Timeline

| Task | Estimate | Dependencies |
|------|----------|--------------|
| 1. Placeholder Parser | 3 hours | None |
| 2. Document Generator | 4 hours | Task 1 |
| 3. API Endpoints | 2 hours | Tasks 1, 2 |
| 4. Frontend UI | 3 hours | Task 3 |
| 5. Test Template | 0.5 hours | None |
| 6. Integration Testing | 2 hours | All above |
| **TOTAL** | **14.5 hours** | |

**Estimated Completion: 2-3 working days**

---

## File Structure

```
DNA/
├─ TEMPLATE_SYSTEM_APPROACH.md          ← Architecture doc
├─ PHASE_1_IMPLEMENTATION.md            ← This file
│
├─ test_templates/                       ← Test templates
│  └─ Test_Policy_Template.docx
│
├─ dashboard/
│  ├─ backend/
│  │  ├─ app/
│  │  │  ├─ services/
│  │  │  │  ├─ simple_placeholder_parser.py     ← NEW
│  │  │  │  └─ simple_document_generator.py     ← NEW
│  │  │  │
│  │  │  └─ routes/
│  │  │     └─ template_preview.py              ← NEW
│  │  │
│  │  └─ requirements.txt                        ← UPDATE
│  │
│  └─ frontend/
│     ├─ src/
│     │  └─ app/
│     │     └─ template-preview/
│     │        └─ page.tsx                       ← NEW
│     │
│     └─ package.json                            ← UPDATE
│
└─ storage/                                      ← NEW (gitignored)
   ├─ templates/                                 ← Uploaded templates
   └─ outputs/                                   ← Generated documents
```

---

## Dependencies Installation

### Backend
```bash
# Add to dashboard/backend/requirements.txt
python-docx==1.1.0
docx2pdf==0.1.8  # Windows only

# Install
docker exec dna-backend pip install python-docx docx2pdf
```

### Frontend
```bash
# Add to dashboard/frontend/package.json
docker exec dna-frontend npm install react-pdf@7.5.1

# Or use built-in browser PDF viewer (no dependency needed)
```

---

## Environment Variables

Add to `.env`:
```env
# Storage paths
TEMPLATE_STORAGE_PATH=/app/storage/templates
OUTPUT_STORAGE_PATH=/app/storage/outputs

# PDF conversion (if using LibreOffice instead of docx2pdf)
LIBREOFFICE_PATH=/usr/bin/libreoffice
```

---

## Git Workflow

**Branch:** `feature/template-preview-system`

**Commits:**
1. "Add placeholder parser service"
2. "Add document generator service"
3. "Add template preview API endpoints"
4. "Add frontend template preview page"
5. "Add test template and integration tests"
6. "Update dependencies and documentation"

**PR Title:** "Phase 1: Template Preview System (Proof of Concept)"

---

## Testing Checklist

- [ ] Parser detects all placeholders in test template
- [ ] Parser handles tables correctly
- [ ] Parser handles headers/footers
- [ ] Generator replaces text placeholders
- [ ] Generator inserts images
- [ ] Generator formats dates
- [ ] Generator preserves table formatting
- [ ] PDF conversion works
- [ ] PDF shows correct formatting
- [ ] Frontend uploads file successfully
- [ ] Frontend shows all detected fields
- [ ] Frontend generates preview
- [ ] Frontend displays PDF correctly
- [ ] Error handling works (invalid file, missing data, etc.)

---

## Success Metrics

### Phase 1 Complete When:

✅ Upload template → Fields detected (100% accuracy)
✅ Fill form → Data merged correctly
✅ Generate PDF → Formatting preserved
✅ Preview works → PDF displays in browser

### Demo Ready:
- Upload test template
- Fill with sample data
- Generate preview
- Show PDF with perfect formatting
- **Proves approach works!**

---

## Next Phase Preview

**Phase 2 will add:**
- AI auto-detection (for non-marked templates)
- Template database storage
- Template versioning
- Multiple template support
- Field metadata editor

**But first: Validate Phase 1 works!** 🚀

---

## Current Progress

- [x] Branch created: `feature/template-preview-system`
- [x] Documentation written
- [ ] Task 1: Placeholder Parser (IN PROGRESS)
- [ ] Task 2: Document Generator
- [ ] Task 3: API Endpoints
- [ ] Task 4: Frontend UI
- [ ] Task 5: Test Template
- [ ] Task 6: Integration Testing

**Next Action: Implement Task 1 (Placeholder Parser)** 👇
