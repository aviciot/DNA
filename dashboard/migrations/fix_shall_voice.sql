-- Fix "shall" modal verb in DOCUMENT VOICE rules and example JSON content
-- iso_build: replace the single ban line with an explicit "shall" ban + present-tense examples
UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '- NEVER write "The organization shall..." — write "{{organization_name}} ensures..." or "We conduct..." instead',
    '- NEVER use "shall" as a modal verb — it is ISO audit language, not internal organizational voice
- WRONG: "The organization shall establish..." / "{{organization_name}} shall conduct..."
- RIGHT: "{{organization_name}} establishes..." / "{{organization_name}} conducts..." / "We ensure..."
- Policy statements use simple present tense: establishes, maintains, reviews, ensures, conducts, is responsible for'
)
WHERE prompt_key = 'iso_build';

-- iso_build_formal: replace the incorrect "shall" example in the DOCUMENT VOICE rule
UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '- Policy obligations: "{{organization_name}} shall..." or "All staff must..." — NEVER "The organization shall..."',
    '- Policy obligations: use active present tense — "{{organization_name}} establishes and maintains...", "All staff must..."
- NEVER use "shall" as a modal verb: WRONG "{{organization_name}} shall establish...", RIGHT "{{organization_name}} establishes..."'
)
WHERE prompt_key = 'iso_build_formal';

-- iso_build_formal example JSON: fix "shall maintain" in Purpose section content
UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '{{organization_name}} shall maintain an Information Security Management System (ISMS) to ensure confidentiality, integrity, and availability of information.',
    '{{organization_name}} maintains an Information Security Management System (ISMS) to ensure confidentiality, integrity, and availability of information.'
)
WHERE prompt_key = 'iso_build_formal';

-- iso_build_formal example JSON: fix "shall conduct" in Procedures subsection content
UPDATE dna_app.ai_prompts
SET prompt_text = REPLACE(
    prompt_text,
    '{{organization_name}} shall conduct information security risk assessments at least annually and whenever significant changes occur.',
    '{{organization_name}} conducts information security risk assessments at least annually and whenever significant changes occur.'
)
WHERE prompt_key = 'iso_build_formal';
