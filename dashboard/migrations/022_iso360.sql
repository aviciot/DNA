-- Migration 022: ISO360 Service Flag + Annual Reminder Support
-- Adds ISO360 premium service fields to customer_iso_plans
-- Adds required_documents metadata to iso_standards

-- ── customer_iso_plans: ISO360 fields ──────────────────────────
ALTER TABLE dna_app.customer_iso_plans
    ADD COLUMN IF NOT EXISTS iso360_enabled       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS iso360_activated_at  TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS iso360_annual_month  SMALLINT CHECK (iso360_annual_month BETWEEN 1 AND 12),
    ADD COLUMN IF NOT EXISTS iso360_annual_day    SMALLINT CHECK (iso360_annual_day BETWEEN 1 AND 31);

-- index for scheduler query (daily reminder check)
CREATE INDEX IF NOT EXISTS idx_customer_iso_plans_iso360
    ON dna_app.customer_iso_plans (iso360_enabled, iso360_annual_month, iso360_annual_day)
    WHERE iso360_enabled = TRUE;

-- ── iso_standards: document catalogue per standard ─────────────
ALTER TABLE dna_app.iso_standards
    ADD COLUMN IF NOT EXISTS required_documents JSONB DEFAULT '[]'::jsonb;

-- Seed ISO 27001 required documents (typical set per Annex A + clause 7.5)
UPDATE dna_app.iso_standards
SET required_documents = '[
  {"id": "isms_policy",         "name": "Information Security Policy",               "clause": "5.2",   "mandatory": true},
  {"id": "risk_assessment",     "name": "Risk Assessment & Treatment Plan",           "clause": "8.2",   "mandatory": true},
  {"id": "risk_register",       "name": "Risk Register",                              "clause": "8.2",   "mandatory": true},
  {"id": "soa",                 "name": "Statement of Applicability (SoA)",           "clause": "6.1.3", "mandatory": true},
  {"id": "asset_inventory",     "name": "Asset Inventory",                            "clause": "A.8.1", "mandatory": true},
  {"id": "access_control",      "name": "Access Control Policy",                      "clause": "A.9.1", "mandatory": true},
  {"id": "incident_response",   "name": "Incident Response Procedure",                "clause": "A.16",  "mandatory": true},
  {"id": "business_continuity", "name": "Business Continuity Plan",                   "clause": "A.17",  "mandatory": true},
  {"id": "supplier_policy",     "name": "Supplier Security Policy",                   "clause": "A.15",  "mandatory": false},
  {"id": "training_plan",       "name": "Security Awareness & Training Plan",         "clause": "A.7.2", "mandatory": false}
]'::jsonb
WHERE code = '27001';

-- Seed ISO 27017 required documents (cloud-specific controls)
UPDATE dna_app.iso_standards
SET required_documents = '[
  {"id": "cloud_security_policy", "name": "Cloud Security Policy",                   "clause": "CLD.6.3", "mandatory": true},
  {"id": "shared_responsibility",  "name": "Shared Responsibility Matrix",            "clause": "CLD.9.5", "mandatory": true},
  {"id": "virtual_env_hardening",  "name": "Virtual Environment Hardening Guide",     "clause": "CLD.10",  "mandatory": true},
  {"id": "cloud_asset_inventory",  "name": "Cloud Asset Inventory",                   "clause": "A.8.1",   "mandatory": true},
  {"id": "data_classification",    "name": "Data Classification Policy",              "clause": "A.8.2",   "mandatory": true},
  {"id": "cloud_incident_proc",    "name": "Cloud Incident Response Procedure",       "clause": "A.16",    "mandatory": false}
]'::jsonb
WHERE code = '27017';

-- Seed ISO 9001 required documents
UPDATE dna_app.iso_standards
SET required_documents = '[
  {"id": "quality_policy",       "name": "Quality Policy",                            "clause": "5.2",  "mandatory": true},
  {"id": "quality_manual",       "name": "Quality Manual",                            "clause": "4.4",  "mandatory": false},
  {"id": "context_analysis",     "name": "Context of the Organization",               "clause": "4.1",  "mandatory": true},
  {"id": "risk_opportunities",   "name": "Risks and Opportunities Register",          "clause": "6.1",  "mandatory": true},
  {"id": "quality_objectives",   "name": "Quality Objectives",                        "clause": "6.2",  "mandatory": true},
  {"id": "corrective_actions",   "name": "Corrective Action Log",                     "clause": "10.2", "mandatory": true},
  {"id": "internal_audit_plan",  "name": "Internal Audit Plan",                       "clause": "9.2",  "mandatory": true},
  {"id": "management_review",    "name": "Management Review Minutes",                 "clause": "9.3",  "mandatory": true}
]'::jsonb
WHERE code = '9001';
