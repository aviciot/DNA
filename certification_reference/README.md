# Certification System Reference

This folder contains reference documentation for the intelligent certification document generation system.

## Contents

- **CERTIFICATION_SCHEMA.sql** - Database schema for the `customer` schema with all certification management tables
- **EXAMPLE_PARSED_TEMPLATE.json** - Example of parsed template structure showing how Claude AI extracts fillable fields from Word documents

## Actual Code Location

The running code for the certification system is located in:
- **Backend:** `dashboard/backend/app/routes/` (customers.py, templates.py)
- **Services:** `dashboard/backend/app/services/` (template_parser.py, document_generator.py, etc.)
- **Models:** `dashboard/backend/app/models/`

## Schema Migration

The schema has been migrated to the `customer` schema (not `public`). To apply:
```bash
docker exec -i dna-postgres psql -U dna_user -d dna < ./dashboard/backend/CERTIFICATION_SCHEMA.sql
```

## System Features

- Parse Word templates with Claude AI to extract fillable fields
- Generate documents from 3 input methods:
  - Interview mode (AI asks questions)
  - Free text mode (paste any text)
  - Email thread mode (paste email conversation)
- Track customer certifications and progress
- Version control for documents and templates
