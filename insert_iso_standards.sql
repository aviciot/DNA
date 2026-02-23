-- Insert common ISO standards directly
SET search_path TO dna_app, public;

-- Note: Some standards already exist, this will update them or add new ones
INSERT INTO dna_app.iso_standards (code, name, description, requirements_summary, display_order, active)
VALUES
  -- Information Security Standards
  ('ISO 27001:2022', 'ISO/IEC 27001:2022 - Information Security Management', 'Information Security Management System', 'Requirements for establishing, implementing, maintaining and continually improving an information security management system', 1, true),
  ('ISO 27002:2022', 'ISO/IEC 27002:2022 - Information Security Controls', 'Information Security Controls', 'Code of practice for information security controls', 2, true),
  ('ISO 27017:2015', 'ISO/IEC 27017:2015 - Cloud Security', 'Cloud Security Controls', 'Code of practice for information security controls for cloud services', 3, true),
  ('ISO 27018:2019', 'ISO/IEC 27018:2019 - Cloud Privacy', 'Cloud Privacy Controls', 'Code of practice for protection of personally identifiable information (PII) in public clouds', 4, true),

  -- IT Service Management
  ('ISO 20000:2018', 'ISO/IEC 20000-1:2018 - IT Service Management', 'IT Service Management System', 'Requirements for a service management system', 8, true),

  -- Business Continuity
  ('ISO 22301:2019', 'ISO 22301:2019 - Business Continuity', 'Business Continuity Management System', 'Requirements for a business continuity management system', 9, true),

  -- Risk Management
  ('ISO 31000:2018', 'ISO 31000:2018 - Risk Management', 'Risk Management Guidelines', 'Guidelines for risk management principles and implementation', 10, true)

ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  requirements_summary = EXCLUDED.requirements_summary,
  display_order = EXCLUDED.display_order,
  active = EXCLUDED.active;

-- Show all ISO standards
SELECT code, name, description FROM dna_app.iso_standards ORDER BY display_order;
