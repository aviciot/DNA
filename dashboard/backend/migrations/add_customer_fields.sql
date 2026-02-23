-- Add new fields to customers table
-- Migration: Add website, compliance_email, contract_email, description

ALTER TABLE dna_app.customers
ADD COLUMN IF NOT EXISTS website VARCHAR(500),
ADD COLUMN IF NOT EXISTS compliance_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS contract_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS description TEXT;

-- Add comment
COMMENT ON COLUMN dna_app.customers.website IS 'Company website URL';
COMMENT ON COLUMN dna_app.customers.compliance_email IS 'Email for receiving evidence/documents (automation)';
COMMENT ON COLUMN dna_app.customers.contract_email IS 'Email for contracts (CISO/Legal)';
COMMENT ON COLUMN dna_app.customers.description IS 'Optional notes/description about the customer';
