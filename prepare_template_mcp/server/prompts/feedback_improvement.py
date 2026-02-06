"""
MCP Prompt: Guide Claude on improving user feedback quality.

This prompt teaches Claude how to rewrite unclear feedback to be
more actionable and professional while preserving the user's intent.
"""

from mcp_app import mcp


@mcp.prompt(
    name="improve_feedback",
    description=(
        "Guide for improving user-submitted feedback (bugs, features, improvements). "
        "Teaches Claude how to rewrite unclear descriptions to be more actionable "
        "while preserving the user's original meaning and tone."
    )
)
def improve_feedback_prompt(
    issue_type: str,
    original_title: str,
    original_description: str,
    quality_issues: str = ""
) -> str:
    """
    Generate prompt for improving user feedback.

    Args:
        issue_type: "bug", "feature", or "improvement"
        original_title: User's original title
        original_description: User's original description
        quality_issues: Optional list of detected quality issues

    Returns:
        Formatted prompt for Claude
    """

    issues_section = ""
    if quality_issues:
        issues_section = f"\n**Detected Issues:**\n{quality_issues}\n"

    prompt = f"""You are helping improve user feedback for a software project.

# Original Feedback

**Type:** {issue_type}
**Title:** {original_title}
**Description:** {original_description}
{issues_section}

# Your Task

Rewrite this feedback to be **clear, specific, and actionable** while keeping the user's original meaning.

## Guidelines by Issue Type

### For Bug Reports:
Include these elements (if information is available):
- **What happened?** (Actual behavior)
- **What should happen?** (Expected behavior)
- **Steps to reproduce** (if applicable)
- **Error messages** or relevant details
- **Impact** (who/what is affected)

Example structure:
```
When [doing X], [unexpected behavior Y] occurs instead of [expected behavior Z].

Steps to reproduce:
1. Do X
2. Observe Y

Expected: Z should happen
Actual: Y happens instead

Error: [any error messages]
```

### For Feature Requests:
Include these elements:
- **What feature?** (Clear description)
- **Why needed?** (Use case / problem it solves)
- **How should it work?** (Expected behavior)
- **Who benefits?** (Target users)

Example structure:
```
Add [feature X] to help users [accomplish Y].

Use case: Currently, users need to [workaround]. With [feature X], they could [better approach].

Expected behavior: When users [do Z], the system should [result].

Benefits: [who this helps and why]
```

### For Improvements:
Include these elements:
- **What to improve?** (Current state)
- **Why improve it?** (Current problems/limitations)
- **What would be better?** (Proposed improvement)
- **Expected outcome** (Benefits)

Example structure:
```
Improve [feature X] by [proposed change Y].

Current state: [feature X] currently [limitation].

Problem: This causes [issue] for users who [scenario].

Proposed improvement: Change [X] to [Y] so that [benefit].

Expected outcome: Users will be able to [capability] instead of [current workaround].
```

## Writing Rules

**DO:**
- Be specific and concrete
- Use clear examples
- Include context (when, where, who)
- Structure with bullet points or numbered lists
- Keep the user's tone (casual is fine)
- Preserve technical details
- Add missing information IF you can infer it reasonably

**DON'T:**
- Change the user's core meaning
- Make it overly formal if they wrote casually
- Remove important technical details
- Add information you're guessing about
- Use vague words like "something", "somehow", "maybe"
- Make assumptions about user intent

## Special Cases

**Broken English:**
- Fix grammar and spelling
- Maintain the user's meaning exactly
- Keep it simple and clear

**Too Vague:**
- Ask clarifying questions in [brackets] if needed
- Suggest what information would be helpful
- Work with what's provided

**Too Technical:**
- Keep technical details
- Add brief explanations for context
- Structure for readability

## Output Format

Return a JSON object with this exact structure:

```json
{
  "improved_title": "Clear, specific title (max 100 characters)",
  "improved_description": "Well-structured description following the guidelines above",
  "changes_made": [
    "List of specific improvements made",
    "E.g., 'Added steps to reproduce'",
    "E.g., 'Fixed grammar and spelling'",
    "E.g., 'Removed vague words (something, maybe)'",
    "E.g., 'Added use case explanation'"
  ],
  "questions_for_user": [
    "Optional: Questions to get missing info",
    "Only if critical information is missing"
  ]
}
```

**IMPORTANT:** Return ONLY the JSON object. No markdown code blocks, no extra text.

# Examples

## Example 1: Vague Bug Report

**Original:**
- Title: "something wrong with query"
- Description: "when i run query it not work maybe its slow or something"

**Improved:**
```json
{{
  "improved_title": "Query execution fails or runs very slowly",
  "improved_description": "When executing database queries, the query either fails to complete or runs significantly slower than expected.\\n\\n**Actual behavior:** Query does not complete successfully or takes much longer than usual.\\n\\n**Expected behavior:** Query should execute and return results promptly.\\n\\n**Additional context needed:**\\n- Which specific query is affected?\\n- What error message appears (if any)?\\n- How long does it take vs. expected time?\\n- Does this happen with all queries or specific ones?",
  "changes_made": [
    "Made title specific and clear",
    "Removed vague words (something, maybe)",
    "Added structure with actual vs expected behavior",
    "Added questions to gather missing details"
  ],
  "questions_for_user": [
    "Can you share the specific SQL query that's having issues?",
    "Do you see any error messages?",
    "How long does it take vs. how long you'd expect?"
  ]
}}
```

## Example 2: Good Bug Report (Minor Polish)

**Original:**
- Title: "analyze_oracle_query returns empty plan_details for MERGE statement"
- Description: "i tried to analyze MERGE INTO statement but got empty plan_details array. other queries like SELECT work fine. using oracle 19c."

**Improved:**
```json
{{
  "improved_title": "analyze_oracle_query returns empty plan_details for MERGE statements",
  "improved_description": "When analyzing a MERGE INTO statement using analyze_oracle_query, the returned plan_details array is empty.\\n\\n**Steps to reproduce:**\\n1. Call analyze_oracle_query with a MERGE INTO statement\\n2. Check plan_details in the response\\n3. Observe that it's an empty array\\n\\n**Expected:** plan_details should contain execution plan steps\\n**Actual:** plan_details is []\\n\\n**Environment:** Oracle 19c\\n**Note:** SELECT queries work correctly",
  "changes_made": [
    "Fixed capitalization",
    "Added clear structure with steps to reproduce",
    "Separated expected vs actual behavior",
    "Highlighted environment details"
  ],
  "questions_for_user": []
}}
```

## Example 3: Feature Request

**Original:**
- Title: "add support for mysql"
- Description: "would be nice if we could use this with mysql not just oracle"

**Improved:**
```json
{{
  "improved_title": "Add MySQL database support alongside Oracle",
  "improved_description": "Add support for analyzing MySQL queries in addition to the current Oracle support.\\n\\n**Use case:** Many teams use MySQL databases and would benefit from the same query analysis capabilities currently available for Oracle.\\n\\n**Expected behavior:** Users should be able to connect to MySQL databases and analyze query performance using similar tools to the Oracle analysis features.\\n\\n**Potential features:**\\n- MySQL query analysis (equivalent to analyze_oracle_query)\\n- EXPLAIN plan parsing for MySQL\\n- Index recommendations\\n- Query optimization suggestions\\n\\n**Benefits:** Broader database support would make this MCP useful for more development teams.",
  "changes_made": [
    "Made title more descriptive",
    "Added clear use case",
    "Specified expected behavior",
    "Listed potential features",
    "Explained benefits"
  ],
  "questions_for_user": []
}}
```

---

Now, please improve the user's feedback following these guidelines. Return ONLY the JSON object.
"""

    return prompt
