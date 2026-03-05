-- Per-customer automation config overrides
-- Allows per-customer: contact name, language, recipient list, follow-up limits, enable/disable

CREATE TABLE IF NOT EXISTS dna_app.customer_automation_config (
    customer_id         INTEGER     PRIMARY KEY REFERENCES dna_app.customers(id) ON DELETE CASCADE,
    send_to_emails      TEXT[],                                -- override recipient list (NULL = use customer email fields)
    contact_name        TEXT,                                  -- override greeting name (NULL = use customer.name)
    preferred_language  VARCHAR(5)  NOT NULL DEFAULT 'en',     -- 'en' | 'he'
    max_followups       INTEGER,                               -- NULL = inherit from global automation_config
    followup_delay_days INTEGER,                               -- NULL = inherit from global automation_config
    send_window_start   TIME,
    send_window_end     TIME,
    enabled             BOOLEAN     NOT NULL DEFAULT TRUE,
    notes               TEXT,
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW()
);
