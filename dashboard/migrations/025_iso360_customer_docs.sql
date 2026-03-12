-- Migration 025: Allow NULL template_id on customer_documents for ISO360 activity rows
-- ISO360 activity documents are not linked to a catalog template

ALTER TABLE dna_app.customer_documents
    ALTER COLUMN template_id DROP NOT NULL;
