"""Apply ai_prompts updates for migration 024."""
import asyncpg
import asyncio

RECURRING_BLOCK = (
    "--- ISO360 RECURRING ACTIVITIES (REQUIRED) ---\n\n"
    "For EVERY template in the \"templates\" array, add a \"recurring_activities\" array "
    "listing the compliance activities that must be performed regularly for that template's functional area.\n\n"
    "Additionally, add a top-level \"iso_recurring_activities\" array for cross-cutting activities "
    "that span all templates (e.g. management review, internal audit, risk assessment cycle).\n\n"
    "Each activity object:\n"
    "{\n"
    "  \"key\": \"globally_unique_lowercase_underscore\",\n"
    "  \"title\": \"Action-oriented activity name\",\n"
    "  \"iso_clause\": \"Exact clause or control ref e.g. 9.2 or A.8.2\",\n"
    "  \"type\": \"review\" | \"operational_activity\" | \"record\",\n"
    "  \"update_frequency\": \"monthly\" | \"quarterly\" | \"yearly\" | \"event_based\",\n"
    "  \"description\": \"One sentence - what must be done and why it satisfies the clause\",\n"
    "  \"related_placeholder_keys\": [\"keys from placeholder_dictionary that capture evidence\"]\n"
    "}\n\n"
    "RULES:\n"
    "- Activities MUST derive from actual clauses/controls in the standard - no invented activities\n"
    "- Each activity MUST include a real iso_clause reference\n"
    "- Do NOT include document metadata fields (version, approved_by, effective_date, prepared_by, "
    "reviewed_by, document_id) as activities - these are document scaffolding, not compliance activities\n"
    "- related_placeholder_keys MUST reference actual keys from placeholder_dictionary\n"
    "- Aim for 2-5 activities per template; 2-4 entries in iso_recurring_activities\n"
    "- Keys must be globally unique across all activities and iso_recurring_activities\n\n"
    "Updated JSON structure (add these fields to the existing schema):\n"
    "{\n"
    "  \"summary\": {\"...\": \"existing fields unchanged\"},\n"
    "  \"placeholder_dictionary\": [\"...existing...\"],\n"
    "  \"iso_recurring_activities\": [\n"
    "    {\n"
    "      \"key\": \"internal_isms_audit\",\n"
    "      \"title\": \"Annual Internal ISMS Audit\",\n"
    "      \"iso_clause\": \"9.2\",\n"
    "      \"type\": \"review\",\n"
    "      \"update_frequency\": \"yearly\",\n"
    "      \"description\": \"Conduct planned internal audits to verify ISMS conformance and effectiveness\",\n"
    "      \"related_placeholder_keys\": [\"internal_audit_programme\"]\n"
    "    }\n"
    "  ],\n"
    "  \"templates\": [\n"
    "    {\n"
    "      \"name\": \"...\",\n"
    "      \"covered_clauses\": [\"...\"],\n"
    "      \"covered_controls\": [\"...\"],\n"
    "      \"fixed_sections\": [\"...\"],\n"
    "      \"recurring_activities\": [\n"
    "        {\n"
    "          \"key\": \"user_access_review\",\n"
    "          \"title\": \"Quarterly User Access Review\",\n"
    "          \"iso_clause\": \"A.8.2\",\n"
    "          \"type\": \"review\",\n"
    "          \"update_frequency\": \"quarterly\",\n"
    "          \"description\": \"Verify all user access rights remain appropriate and authorized\",\n"
    "          \"related_placeholder_keys\": [\"access_review_results\", \"reviewed_by\"]\n"
    "        }\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "ISO STANDARD TEXT:"
)

NEW_USER_PROMPT = (
    "Generate an ISO360 task template for the following compliance requirement:\n\n"
    "activity_key: {{placeholder_key}}\n"
    "activity_title: {{placeholder_key}}\n"
    "type: {{type}}\n"
    "update_frequency: {{update_frequency}}\n"
    "iso_clause: {{iso_clause}}\n"
    "template_area: {{category}}\n"
    "iso_standard: {{iso_standard_name}}\n"
    "description: {{description}}\n\n"
    "Return only the JSON template - no explanation, no markdown."
)


async def main():
    conn = await asyncpg.connect(
        "postgresql://dna_user:dna_password_dev@dna-postgres/dna"
    )

    rows = await conn.fetch(
        "SELECT prompt_key, prompt_text FROM dna_app.ai_prompts "
        "WHERE prompt_key IN ('iso_build', 'iso_build_formal') AND is_active = TRUE"
    )
    print(f"Found {len(rows)} iso_build prompts")

    for row in rows:
        old_text = row["prompt_text"]
        marker = "ISO STANDARD TEXT:"
        if marker in old_text:
            new_text = old_text.replace(marker, RECURRING_BLOCK)
            await conn.execute(
                "UPDATE dna_app.ai_prompts SET prompt_text = $1 WHERE prompt_key = $2",
                new_text, row["prompt_key"]
            )
            print(f"  Updated {row['prompt_key']} - recurring block inserted")
        else:
            print(f"  WARN: 'ISO STANDARD TEXT:' marker not found in {row['prompt_key']}")

    r = await conn.execute(
        "UPDATE dna_app.ai_prompts SET prompt_text = $1 WHERE prompt_key = 'iso360_template_user'",
        NEW_USER_PROMPT,
    )
    print(f"Updated iso360_template_user: {r}")

    await conn.close()
    print("Done.")


asyncio.run(main())
