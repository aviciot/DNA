-- DNA Cleanup: Drop dead/unused tables
-- Run this AFTER sanity check confirms the app is working correctly
-- Safe to run: all tables below have 0 live rows and no active code references

BEGIN;

DROP TABLE IF EXISTS dna_app.template_reviews CASCADE;
DROP TABLE IF EXISTS dna_app.iso_templates CASCADE;
DROP TABLE IF EXISTS dna_app.customer_responses CASCADE;
DROP TABLE IF EXISTS dna_app.conversations CASCADE;
DROP TABLE IF EXISTS dna_app.customer_document_history CASCADE;
DROP TABLE IF EXISTS dna_app.documents CASCADE;
DROP TABLE IF EXISTS dna_app.customer_interview_sessions CASCADE;
DROP TABLE IF EXISTS dna_app.scheduler_jobs CASCADE;
DROP TABLE IF EXISTS dna_app.collection_requests CASCADE;
DROP TABLE IF EXISTS dna_app.customer_storage_files CASCADE;
DROP TABLE IF EXISTS dna_app.generated_documents CASCADE;

-- Drop entire legacy customer schema
DROP SCHEMA IF EXISTS customer CASCADE;

COMMIT;
