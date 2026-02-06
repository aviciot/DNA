-- DNA Auth Service - Roles & Permissions Migration
-- ================================================
-- Creates roles table and permissions system for granular access control

-- Create roles table
CREATE TABLE IF NOT EXISTS auth.roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_system BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default system roles
INSERT INTO auth.roles (name, description, permissions, is_system) VALUES
('admin', 'Full system access', 
 '{"tabs": ["dashboard", "customers", "documents", "admin", "iam"], "chatwidget": true}'::jsonb, 
 true),
('viewer', 'Read-only access',
 '{"tabs": ["dashboard", "customers", "documents"], "chatwidget": true}'::jsonb,
 true)
ON CONFLICT (name) DO NOTHING;

-- Add role_id column to users table (nullable for migration)
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES auth.roles(id);

-- Migrate existing users to use role_id
UPDATE auth.users SET role_id = (SELECT id FROM auth.roles WHERE name = auth.users.role) WHERE role_id IS NULL;

-- Create index on role_id
CREATE INDEX IF NOT EXISTS idx_users_role_id ON auth.users(role_id);

-- Create updated_at trigger for roles
CREATE OR REPLACE FUNCTION auth.update_roles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_roles_updated_at
    BEFORE UPDATE ON auth.roles
    FOR EACH ROW
    EXECUTE FUNCTION auth.update_roles_updated_at();

COMMENT ON TABLE auth.roles IS 'User roles with granular permissions';
COMMENT ON COLUMN auth.roles.permissions IS 'JSON object with tabs array and chatwidget boolean';
COMMENT ON COLUMN auth.roles.is_system IS 'System roles cannot be deleted or renamed';
