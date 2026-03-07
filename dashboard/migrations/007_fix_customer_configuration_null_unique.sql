-- Fix unique index on customer_configuration to handle NULL customer_id
-- Standard btree unique index treats NULL != NULL, so ON CONFLICT never fires for global rows.
-- Replace with two partial indexes: one for NULL customer_id, one for non-NULL.

ALTER TABLE dna_app.customer_configuration DROP CONSTRAINT IF EXISTS customer_configuration_customer_id_config_type_config_key_key;

CREATE UNIQUE INDEX customer_configuration_global_unique
    ON dna_app.customer_configuration (config_type, config_key)
    WHERE customer_id IS NULL;

CREATE UNIQUE INDEX customer_configuration_customer_unique
    ON dna_app.customer_configuration (customer_id, config_type, config_key)
    WHERE customer_id IS NOT NULL;
