-- =============================================================================
-- DNA Database Initialization Script
-- =============================================================================
-- Purpose: Create schemas and initial tables for DNA ISO certification dashboard
-- Schemas: auth (authentication), dna_app (application data)
-- =============================================================================

-- Create schemas
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS dna_app;

-- Set search path to include both schemas
SET search_path TO auth, dna_app, public;

-- =============================================================================
-- AUTH SCHEMA - Authentication and Authorization
-- =============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS auth.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT role_valid CHECK (role IN ('admin', 'viewer'))
);

-- Sessions table
CREATE TABLE IF NOT EXISTS auth.sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    
    CONSTRAINT session_id_format CHECK (session_id ~ '^[a-f0-9-]+$')
);

-- Roles table (reference data)
CREATE TABLE IF NOT EXISTS auth.roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes on auth tables
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON auth.users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON auth.users(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON auth.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON auth.sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON auth.sessions(expires_at);

-- =============================================================================
-- DNA_APP SCHEMA - Application Data
-- =============================================================================

-- ISO Templates table
CREATE TABLE IF NOT EXISTS dna_app.iso_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    iso_standard VARCHAR(50) NOT NULL,
    template_data JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Customers table
CREATE TABLE IF NOT EXISTS dna_app.customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    contact_person VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata JSONB,
    created_by INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT status_valid CHECK (status IN ('active', 'inactive', 'pending', 'completed'))
);

-- Documents table
CREATE TABLE IF NOT EXISTS dna_app.documents (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    template_id INTEGER NOT NULL REFERENCES dna_app.iso_templates(id),
    title VARCHAR(255) NOT NULL,
    document_data JSONB NOT NULL,
    completion_percentage INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    assigned_to INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT completion_range CHECK (completion_percentage BETWEEN 0 AND 100),
    CONSTRAINT status_valid CHECK (status IN ('draft', 'in_progress', 'review', 'completed', 'rejected'))
);

-- AI Tasks table (for AI monitoring and alerts)
CREATE TABLE IF NOT EXISTS dna_app.ai_tasks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES dna_app.documents(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    ai_suggestion TEXT,
    assigned_to INTEGER REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT task_type_valid CHECK (task_type IN ('missing_info', 'review_required', 'escalation', 'auto_request')),
    CONSTRAINT priority_valid CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    CONSTRAINT status_valid CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))
);

-- Conversations table (chat history with Claude)
CREATE TABLE IF NOT EXISTS dna_app.conversations (
    id SERIAL PRIMARY KEY,
    conversation_id UUID UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_role VARCHAR(20) NOT NULL,
    message_content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT role_valid CHECK (message_role IN ('user', 'assistant', 'system'))
);

-- Create indexes on dna_app tables
CREATE INDEX IF NOT EXISTS idx_iso_templates_is_active ON dna_app.iso_templates(is_active);
CREATE INDEX IF NOT EXISTS idx_customers_status ON dna_app.customers(status);
CREATE INDEX IF NOT EXISTS idx_documents_customer_id ON dna_app.documents(customer_id);
CREATE INDEX IF NOT EXISTS idx_documents_template_id ON dna_app.documents(template_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON dna_app.documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_assigned_to ON dna_app.documents(assigned_to);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_document_id ON dna_app.ai_tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_status ON dna_app.ai_tasks(status);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_assigned_to ON dna_app.ai_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_conversations_conversation_id ON dna_app.conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON dna_app.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON dna_app.conversations(created_at);

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Insert default roles
INSERT INTO auth.roles (name, description, permissions) VALUES
('admin', 'Administrator with full access', '{"dashboard": ["read", "write"], "templates": ["read", "write"], "customers": ["read", "write"], "documents": ["read", "write"], "admin": ["read", "write"], "chat": ["use"]}'::jsonb),
('viewer', 'Viewer with read-only access', '{"dashboard": ["read"], "customers": ["read"], "documents": ["read"]}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- Insert default admin user (password: admin123)
-- Password hash generated with bcrypt rounds=12
INSERT INTO auth.users (email, password_hash, full_name, role, is_active) VALUES
('admin@dna.local', '$2b$12$tVYqV2qsnGojx6EWr6PDje5jtUIw736sa6nmzBSHSLAcecV7XViQe', 'DNA Administrator', 'admin', true)
ON CONFLICT (email) DO NOTHING;

-- Insert sample ISO template
INSERT INTO dna_app.iso_templates (name, description, iso_standard, template_data, created_by) VALUES
('ISO 9001:2015 Quality Management', 'Standard template for ISO 9001:2015 certification', 'ISO 9001:2015', 
'{"sections": [{"id": "4", "title": "Context of the Organization", "fields": ["understanding_org", "understanding_needs", "scope", "qms"]}, {"id": "5", "title": "Leadership", "fields": ["leadership_commitment", "policy", "roles_responsibilities"]}, {"id": "6", "title": "Planning", "fields": ["risk_opportunities", "quality_objectives", "planning_changes"]}]}'::jsonb,
(SELECT id FROM auth.users WHERE email = 'admin@dna.local'))
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Functions and Triggers
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_iso_templates_updated_at BEFORE UPDATE ON dna_app.iso_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON dna_app.customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON dna_app.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Cleanup expired sessions function
CREATE OR REPLACE FUNCTION auth.cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM auth.sessions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Grants
-- =============================================================================

-- Grant usage on schemas
GRANT USAGE ON SCHEMA auth TO dna_user;
GRANT USAGE ON SCHEMA dna_app TO dna_user;

-- Grant all privileges on tables to dna_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth TO dna_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA dna_app TO dna_user;

-- Grant sequence privileges
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO dna_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA dna_app TO dna_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES TO dna_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON SEQUENCES TO dna_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA dna_app GRANT ALL ON TABLES TO dna_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA dna_app GRANT ALL ON SEQUENCES TO dna_user;

-- =============================================================================
-- Completion Message
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================================================';
    RAISE NOTICE 'DNA Database initialization completed successfully!';
    RAISE NOTICE '=============================================================================';
    RAISE NOTICE 'Schemas created: auth, dna_app';
    RAISE NOTICE 'Default admin user: admin@dna.local (password: admin123)';
    RAISE NOTICE 'Sample ISO template created';
    RAISE NOTICE '=============================================================================';
END $$;
