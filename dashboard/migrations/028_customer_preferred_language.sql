-- Migration 028: Add preferred_language to customers and customer_iso_plans
-- customers: single source of truth for all communication language
-- customer_iso_plans: per-plan override (NULL = inherit from customer)

ALTER TABLE dna_app.customers
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NOT NULL DEFAULT 'en';

ALTER TABLE dna_app.customer_iso_plans
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NULL;
