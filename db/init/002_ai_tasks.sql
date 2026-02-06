-- =============================================================================
-- DNA Database Migration 002: AI Task Management
-- =============================================================================
-- Purpose: Add tables for async AI operations, LLM provider management, and template reviews
-- Schema: dna_app
-- Version: 002
-- Date: 2026-02-07
-- =============================================================================

-- Set search path
SET search_path TO dna_app, auth, public;

-- =============================================================================
-- LLM PROVIDERS - Multi-LLM Configuration
-- =============================================================================

CREATE TABLE IF NOT EXISTS dna_app.llm_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,           -- 'claude', 'openai', 'gemini'
    display_name VARCHAR(100) NOT NULL,         -- 'Claude Sonnet 4.5', 'GPT-4o'
    model VARCHAR(100) NOT NULL,                -- 'claude-sonnet-4-5-20250929'
    api_key_env VARCHAR(100) NOT NULL,          -- Environment variable name
    cost_per_1k_input DECIMAL(10,4),           -- Cost per 1K input tokens
    cost_per_1k_output DECIMAL(10,4),          -- Cost per 1K output tokens
    max_tokens INTEGER DEFAULT 4096,
    enabled BOOLEAN DEFAULT true,
    is_default_parser BOOLEAN DEFAULT false,     -- Default for template parsing
    is_default_reviewer BOOLEAN DEFAULT false,   -- Default for template review
    is_default_chat BOOLEAN DEFAULT false,       -- Default for chat interactions
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT provider_name_valid CHECK (name ~ '^[a-z0-9_-]+$')
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_providers_name ON dna_app.llm_providers(name);
CREATE INDEX IF NOT EXISTS idx_llm_providers_enabled ON dna_app.llm_providers(enabled);
CREATE INDEX IF NOT EXISTS idx_llm_providers_default_parser ON dna_app.llm_providers(is_default_parser) WHERE is_default_parser = true;

-- =============================================================================
-- AI TASKS - Async AI Operations Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS dna_app.ai_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,             -- 'template_parse', 'template_review', 'document_generate'
    related_id UUID,                             -- template_id or document_id (no FK since could be different tables)
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'cancelled'
    progress INTEGER DEFAULT 0,                  -- 0-100 percentage
    current_step TEXT,                           -- "Parsing section 3 of 12..."
    llm_provider_id UUID REFERENCES dna_app.llm_providers(id),
    llm_provider VARCHAR(50),                    -- Denormalized for history (in case provider deleted)
    llm_model VARCHAR(100),
    result JSONB,                                -- Parsed template, review feedback, or generated document
    error TEXT,                                  -- Error message if failed
    cost_usd DECIMAL(10,4),                     -- Actual API cost for this task
    tokens_input INTEGER,                        -- Input tokens used
    tokens_output INTEGER,                       -- Output tokens used
    duration_seconds INTEGER,                    -- How long the task took
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by INTEGER REFERENCES auth.users(id),
    
    CONSTRAINT task_type_valid CHECK (task_type IN ('template_parse', 'template_review', 'document_generate')),
    CONSTRAINT status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    CONSTRAINT progress_range CHECK (progress >= 0 AND progress <= 100)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_ai_tasks_status ON dna_app.ai_tasks(status);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_type ON dna_app.ai_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_related ON dna_app.ai_tasks(related_id);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_created_by ON dna_app.ai_tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_created_at ON dna_app.ai_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_tasks_provider ON dna_app.ai_tasks(llm_provider_id);

-- =============================================================================
-- TEMPLATE REVIEWS - Quality Validation Results
-- =============================================================================

CREATE TABLE IF NOT EXISTS dna_app.template_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL,                   -- References customer.certification_templates(id)
    task_id UUID REFERENCES dna_app.ai_tasks(id),
    reviewer_llm VARCHAR(50),                    -- Which LLM performed the review
    overall_score INTEGER,                       -- 0-100 overall quality score
    completeness_score INTEGER,                  -- 0-100 how complete is the template
    compliance_score INTEGER,                    -- 0-100 ISO compliance score
    missing_fields JSONB,                        -- ["field1", "field2", ...]
    suggestions JSONB,                           -- [{field, issue, suggestion}, ...]
    compliance_issues JSONB,                     -- [{section, issue, severity}, ...]
    review_notes TEXT,                           -- Free-form notes from reviewer
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES auth.users(id),
    
    CONSTRAINT overall_score_range CHECK (overall_score >= 0 AND overall_score <= 100),
    CONSTRAINT completeness_score_range CHECK (completeness_score >= 0 AND completeness_score <= 100),
    CONSTRAINT compliance_score_range CHECK (compliance_score >= 0 AND compliance_score <= 100)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_template_reviews_template ON dna_app.template_reviews(template_id);
CREATE INDEX IF NOT EXISTS idx_template_reviews_task ON dna_app.template_reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_template_reviews_created_at ON dna_app.template_reviews(created_at DESC);

-- =============================================================================
-- SEED DATA - Initial LLM Providers
-- =============================================================================

-- Insert Claude Sonnet 4.5 as default parser
INSERT INTO dna_app.llm_providers (
    name, 
    display_name, 
    model, 
    api_key_env, 
    cost_per_1k_input, 
    cost_per_1k_output, 
    max_tokens, 
    enabled, 
    is_default_parser,
    is_default_chat
) VALUES (
    'claude',
    'Claude Sonnet 4.5',
    'claude-sonnet-4-5-20250929',
    'ANTHROPIC_API_KEY',
    0.0030,  -- $3 per million input tokens
    0.0150,  -- $15 per million output tokens
    8192,
    true,
    true,  -- Default for parsing
    true   -- Default for chat
) ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    model = EXCLUDED.model,
    api_key_env = EXCLUDED.api_key_env,
    cost_per_1k_input = EXCLUDED.cost_per_1k_input,
    cost_per_1k_output = EXCLUDED.cost_per_1k_output,
    max_tokens = EXCLUDED.max_tokens,
    updated_at = NOW();

-- Insert OpenAI GPT-4 as placeholder (for future use)
INSERT INTO dna_app.llm_providers (
    name, 
    display_name, 
    model, 
    api_key_env, 
    cost_per_1k_input, 
    cost_per_1k_output, 
    max_tokens, 
    enabled,
    is_default_reviewer
) VALUES (
    'openai',
    'GPT-4 Turbo',
    'gpt-4-turbo-preview',
    'OPENAI_API_KEY',
    0.0100,  -- $10 per million input tokens
    0.0300,  -- $30 per million output tokens
    4096,
    false,  -- Disabled until API key provided
    true    -- Will be default reviewer when enabled
) ON CONFLICT (name) DO NOTHING;

-- Insert Google Gemini as placeholder (for future use)
INSERT INTO dna_app.llm_providers (
    name, 
    display_name, 
    model, 
    api_key_env, 
    cost_per_1k_input, 
    cost_per_1k_output, 
    max_tokens, 
    enabled
) VALUES (
    'gemini',
    'Gemini Pro',
    'gemini-pro',
    'GOOGLE_API_KEY',
    0.0005,  -- $0.50 per million input tokens
    0.0015,  -- $1.50 per million output tokens
    8192,
    false  -- Disabled until API key provided
) ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Show created tables
SELECT 
    schemaname, 
    tablename 
FROM pg_tables 
WHERE schemaname = 'dna_app' 
    AND tablename IN ('llm_providers', 'ai_tasks', 'template_reviews')
ORDER BY tablename;

-- Show LLM providers
SELECT 
    name,
    display_name,
    model,
    enabled,
    is_default_parser,
    is_default_reviewer,
    is_default_chat
FROM dna_app.llm_providers
ORDER BY name;

-- Migration complete
\echo '✅ Migration 002 complete: AI Task Management tables created'
