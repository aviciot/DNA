"""
Quick test: verify Gemini returns valid JSON with a tiny ISO-like prompt.
Run inside the container: docker exec dna-ai-service python test_gemini_json.py
"""
import asyncio
import json
import os
from gemini_client import get_gemini_client

MINI_PROMPT = """You are a compliance expert. Return ONLY valid JSON, no extra text.

{
  "summary": {
    "standard_name": "ISO TEST",
    "overview": "Test standard",
    "total_clauses": 2,
    "total_controls": 3,
    "key_themes": ["Security"],
    "document_count": 1
  },
  "templates": [
    {
      "name": "TEST 01 Policy",
      "covered_clauses": ["4.1"],
      "covered_controls": ["A.5.1"],
      "fixed_sections": [
        {
          "id": "scope",
          "title": "Scope",
          "content": "This policy applies to {{organization_name}}.",
          "section_type": "policy_statement",
          "iso_reference": "4.1"
        }
      ],
      "fillable_sections": [
        {
          "id": "org_name",
          "title": "Organization Name",
          "placeholder": "{{organization_name}}",
          "question": "What is your organization name?",
          "is_mandatory": true,
          "iso_reference": "4.1",
          "semantic_tags": ["organization"],
          "automation_source": "manual",
          "auto_fillable": false,
          "trigger_event": "annual_review"
        }
      ]
    }
  ]
}

Return exactly the above JSON."""


async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set")
        return

    print(f"Testing Gemini JSON extraction with model: {model}")
    client = get_gemini_client(api_key=api_key, model=model, max_tokens=4096)

    result = await client.call(prompt=MINI_PROMPT, temperature=0.1)

    print(f"Finish reason check - output tokens: {result['usage']['output_tokens']}")
    print(f"Raw content length: {len(result['content'])} chars")
    print(f"Raw content preview: {result['content'][:200]}")

    json_str = client.extract_json(result["content"])
    data = json.loads(json_str)

    print(f"\n✓ JSON parsed OK")
    print(f"  summary.standard_name: {data['summary']['standard_name']}")
    print(f"  templates count: {len(data['templates'])}")
    print(f"  first template: {data['templates'][0]['name']}")
    print(f"\nGemini JSON extraction is working correctly.")


asyncio.run(main())
