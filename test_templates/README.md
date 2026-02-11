# Test Templates

This directory contains test templates for Phase 1 validation.

## Test_Policy_Template.docx

A sample Information Security Policy template with the following placeholders:

### Placeholders Used:

1. **{{logo|image|required}}** - Company logo (image)
2. **{{company_name}}** - Company legal name (text)
3. **{{effective_date|date}}** - Policy effective date (date)
4. **{{ciso_name}}** - CISO full name (text)
5. **{{backup_solution|textarea}}** - Backup solution description (textarea)

### Test Data:

```json
{
  "company_name": "Acme Corporation",
  "effective_date": "2026-02-11",
  "ciso_name": "John Smith",
  "backup_solution": "We use AWS S3 for daily automated backups with 30-day retention and versioning enabled. Backups are encrypted at rest and in transit."
}
```

### Creating the Template:

Since we can't create actual DOCX files programmatically here, you need to:

1. Open Microsoft Word
2. Create a new document
3. Copy the content from `TEMPLATE_CONTENT.txt`
4. Save as `Test_Policy_Template.docx`

Or use the provided template if available.

## Usage

1. Navigate to http://localhost:3003/template-preview
2. Upload `Test_Policy_Template.docx`
3. Fill the detected fields
4. Generate preview
5. Verify PDF output looks correct

## Expected Results

- ✅ All 5 placeholders detected
- ✅ Types correctly identified (image, text, date, textarea)
- ✅ Required flag set for logo
- ✅ Form renders with appropriate inputs
- ✅ PDF generated with filled data
- ✅ Formatting preserved (table, headings, structure)
