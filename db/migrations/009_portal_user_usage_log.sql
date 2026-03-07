-- Grant portal_user access to ai_usage_log for budget checks and usage logging
GRANT SELECT, INSERT ON dna_app.ai_usage_log TO portal_user;
