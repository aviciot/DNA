ALTER TABLE dna_app.llm_providers
  ADD COLUMN supports_pdf boolean NOT NULL DEFAULT false,
  ADD COLUMN send_as_strategy varchar(20) NOT NULL DEFAULT 'extract_text'
    CONSTRAINT send_as_strategy_valid CHECK (send_as_strategy IN ('extract_text', 'native_pdf'));

-- Gemini supports native PDF via File API; others use text extraction
UPDATE dna_app.llm_providers SET supports_pdf = true,  send_as_strategy = 'native_pdf'  WHERE name = 'gemini';
UPDATE dna_app.llm_providers SET supports_pdf = false, send_as_strategy = 'extract_text' WHERE name IN ('openai', 'claude');
