-- DNA Backend - Certification Management Schema
-- ================================================
-- Complete schema for document templates, customers, and certifications

-- Create customer schema
CREATE SCHEMA IF NOT EXISTS customer;

-- Customers table
CREATE TABLE IF NOT EXISTS customer.customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    secondary_email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    business_area TEXT,
    notes TEXT,
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Certifications table (e.g., ISO 27001, ISO 9001, etc.)
CREATE TABLE IF NOT EXISTS customer.certifications (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    requirements_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Certification templates (parsed Word documents)
CREATE TABLE IF NOT EXISTS customer.certification_templates (
    id SERIAL PRIMARY KEY,
    certification_id INTEGER REFERENCES customer.certifications(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    document_type VARCHAR(50) NOT NULL, -- 'policy', 'procedure', 'form', 'checklist'
    template_structure JSONB NOT NULL, -- Parsed document with tags
    fields_metadata JSONB NOT NULL, -- Field definitions: [{name, type, required, description}]
    original_filename VARCHAR(255),
    file_url TEXT,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Customer certifications (which certifications is customer pursuing)
CREATE TABLE IF NOT EXISTS customer.customer_certifications (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customer.customers(id) ON DELETE CASCADE,
    certification_id INTEGER NOT NULL REFERENCES customer.certifications(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'not_started', -- not_started, in_progress, under_review, completed, expired
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,
    start_date DATE,
    target_completion_date DATE,
    actual_completion_date DATE,
    assigned_to INTEGER REFERENCES auth.users(id),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(customer_id, certification_id)
);

-- Customer documents (filled templates for specific customers)
CREATE TABLE IF NOT EXISTS customer.customer_documents (
    id SERIAL PRIMARY KEY,
    customer_certification_id INTEGER NOT NULL REFERENCES customer.customer_certifications(id) ON DELETE CASCADE,
    template_id INTEGER NOT NULL REFERENCES customer.certification_templates(id) ON DELETE CASCADE,
    document_name VARCHAR(255) NOT NULL,
    filled_data JSONB NOT NULL, -- Key-value pairs of tag -> filled value
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft, in_progress, pending_review, approved, rejected
    completion_percentage DECIMAL(5,2) DEFAULT 0.00,
    assigned_to INTEGER REFERENCES auth.users(id),
    reviewed_by INTEGER REFERENCES auth.users(id),
    reviewed_at TIMESTAMP,
    notes TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_customers_email ON customer.customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customer.customers(created_at);
CREATE INDEX IF NOT EXISTS idx_certifications_code ON customer.certifications(code);
CREATE INDEX IF NOT EXISTS idx_certification_templates_cert_id ON customer.certification_templates(certification_id);
CREATE INDEX IF NOT EXISTS idx_customer_certifications_customer ON customer.customer_certifications(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_certifications_status ON customer.customer_certifications(status);
CREATE INDEX IF NOT EXISTS idx_customer_documents_cert_id ON customer.customer_documents(customer_certification_id);
CREATE INDEX IF NOT EXISTS idx_customer_documents_status ON customer.customer_documents(status);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION customer.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customer.customers
    FOR EACH ROW EXECUTE FUNCTION customer.update_updated_at_column();

CREATE TRIGGER update_certifications_updated_at BEFORE UPDATE ON customer.certifications
    FOR EACH ROW EXECUTE FUNCTION customer.update_updated_at_column();

CREATE TRIGGER update_certification_templates_updated_at BEFORE UPDATE ON customer.certification_templates
    FOR EACH ROW EXECUTE FUNCTION customer.update_updated_at_column();

CREATE TRIGGER update_customer_certifications_updated_at BEFORE UPDATE ON customer.customer_certifications
    FOR EACH ROW EXECUTE FUNCTION customer.update_updated_at_column();

CREATE TRIGGER update_customer_documents_updated_at BEFORE UPDATE ON customer.customer_documents
    FOR EACH ROW EXECUTE FUNCTION customer.update_updated_at_column();

-- Insert sample certifications
INSERT INTO customer.certifications (code, name, description, requirements_count) VALUES
    ('ISO-27001', 'ISO/IEC 27001:2022', 'Information Security Management System', 93),
    ('ISO-9001', 'ISO 9001:2015', 'Quality Management System', 10),
    ('ISO-14001', 'ISO 14001:2015', 'Environmental Management System', 10),
    ('SOC-2', 'SOC 2 Type II', 'Service Organization Control 2', 64),
    ('GDPR', 'GDPR Compliance', 'General Data Protection Regulation', 11)
ON CONFLICT (code) DO NOTHING;

-- Comments
COMMENT ON SCHEMA customer IS 'Customer certification management data';
COMMENT ON TABLE customer.customers IS 'Customer organizations seeking certifications';
COMMENT ON TABLE customer.certifications IS 'Available certification types (ISO standards, etc.)';
COMMENT ON TABLE customer.certification_templates IS 'Document templates with AI-parsed fields';
COMMENT ON TABLE customer.customer_certifications IS 'Certifications assigned to customers with progress tracking';
COMMENT ON TABLE customer.customer_documents IS 'Customer-specific documents filled from templates';
COMMENT ON COLUMN customer.certification_templates.template_structure IS 'Parsed document content with {{tags}}';
COMMENT ON COLUMN public.certification_templates.fields_metadata IS 'Definitions for each fillable field';
COMMENT ON COLUMN public.customer_documents.filled_data IS 'User-provided values for template tags';
