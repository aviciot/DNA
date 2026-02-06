"""
Feedback quality analysis and improvement - LLM-powered content enhancement.

GENERIC MODULE: Copy to any MCP for quality checking.
Works with any issue type (bug/feature/improvement).
"""

import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FeedbackQualityAnalyzer:
    """
    Analyzes feedback quality and generates improvement suggestions.
    Uses heuristic analysis + LLM-powered rewriting for unclear content.
    """

    def __init__(self):
        # Quality scoring weights
        self.weights = {
            "vague_language": -2,
            "missing_details": -3,
            "grammar_issues": -1,
            "good_structure": +2,
            "specific_examples": +2,
            "clear_steps": +2,
        }

        # Vague words that reduce quality score
        self.vague_words = [
            "something", "somehow", "maybe", "sometimes", "stuff",
            "things", "whatever", "kind of", "sort of", "etc",
            "and so on", "or something", "i think", "probably"
        ]

        # Required elements by issue type
        self.required_elements = {
            "bug": ["what happened", "expected behavior", "actual behavior"],
            "feature": ["what feature", "why needed", "expected behavior"],
            "improvement": ["what to improve", "why", "expected outcome"]
        }

    def analyze_feedback_quality(
        self,
        issue_type: str,
        title: str,
        description: str
    ) -> Dict:
        """
        Analyze feedback quality and return score + suggestions.

        Args:
            issue_type: "bug", "feature", or "improvement"
            title: Issue title
            description: Issue description

        Returns:
            {
                "quality_score": 0-10,
                "issues_found": [list of problems],
                "suggestions": [list of improvements],
                "needs_improvement": bool,
                "severity": "low" | "medium" | "high"
            }
        """
        combined = f"{title} {description}".lower()
        issues_found = []
        suggestions = []
        score = 7  # Start with decent score

        # Check 1: Vague language
        vague_count = sum(1 for word in self.vague_words if word in combined)
        if vague_count > 3:
            issues_found.append(f"Contains {vague_count} vague words (something, maybe, etc.)")
            suggestions.append("Be more specific - avoid words like 'something', 'somehow', 'maybe'")
            score += self.weights["vague_language"] * min(vague_count, 3)

        # Check 2: Length and detail
        if len(description) < 50:
            issues_found.append("Description is very short (less than 50 characters)")
            suggestions.append("Add more details to help us understand the issue")
            score += self.weights["missing_details"]

        # Check 3: Missing required elements
        required = self.required_elements.get(issue_type, [])
        missing = []
        for element in required:
            # Simple keyword check
            keywords = element.split()
            if not any(kw in combined for kw in keywords):
                missing.append(element)

        if missing:
            issues_found.append(f"Missing key information: {', '.join(missing)}")
            suggestions.append(f"Please describe: {', '.join(missing)}")
            score += self.weights["missing_details"]

        # Check 4: Grammar and structure
        # Simple checks for common issues
        if re.search(r'\b[a-z][a-z\s]{30,}[.!?]', description):  # Long sentence without caps
            issues_found.append("May have grammar issues (missing capitalization)")
            suggestions.append("Check capitalization and punctuation")
            score += self.weights["grammar_issues"]

        if description.count('.') == 0 and len(description) > 50:
            issues_found.append("No sentence breaks in description")
            suggestions.append("Break text into clear sentences")
            score += self.weights["grammar_issues"]

        # Check 5: Positive signals
        if any(word in combined for word in ["steps to reproduce", "expected", "actual", "should be", "currently"]):
            score += self.weights["good_structure"]

        if re.search(r'1\.|2\.|step 1|step 2|\n-|\n\*', description):
            score += self.weights["clear_steps"]

        if any(word in combined for word in ["example", "for instance", "specifically", "when i"]):
            score += self.weights["specific_examples"]

        # Clamp score to 0-10
        score = max(0, min(10, score))

        # Determine severity
        if score >= 7:
            severity = "low"
            needs_improvement = False
        elif score >= 4:
            severity = "medium"
            needs_improvement = True
        else:
            severity = "high"
            needs_improvement = True

        return {
            "quality_score": round(score, 1),
            "issues_found": issues_found,
            "suggestions": suggestions,
            "needs_improvement": needs_improvement,
            "severity": severity,
            "vague_word_count": vague_count if vague_count > 3 else 0
        }

    def analyze_relevance_simple(
        self,
        issue_type: str,
        title: str,
        description: str
    ) -> Dict:
        """
        Check if feedback is relevant to database query analysis.

        Uses keyword matching (not LLM) for fast validation.

        Returns:
            {
                "is_relevant": bool,
                "category": "relevant" | "unclear" | "irrelevant" | "offtopic",
                "confidence": 0.0-1.0,
                "reason": str,
                "message": str (what to tell user)
            }
        """
        combined = f"{title} {description}".lower()

        # Database-related keywords
        db_keywords = [
            "query", "sql", "database", "table", "column", "index", "performance",
            "execution", "plan", "optimize", "oracle", "mysql", "postgresql", "slow",
            "timeout", "analyze", "explain", "cache", "schema", "join", "select"
        ]

        # Off-topic keywords that suggest irrelevance
        offtopic_keywords = [
            "pizza", "lyrics", "song", "poem", "joke", "game", "weather",
            "recipe", "music", "movie", "crypto", "lottery", "horoscope",
            "dance", "sing", "fly", "teleport", "magic", "puzzle"
        ]

        # Count matches (use word boundaries to avoid false positives like "sing" in "processing")
        import re
        db_count = sum(1 for kw in db_keywords if re.search(r'\b' + re.escape(kw) + r'\b', combined))
        offtopic_count = sum(1 for kw in offtopic_keywords if re.search(r'\b' + re.escape(kw) + r'\b', combined))

        # Decision logic
        if offtopic_count > 0:
            found_keywords = [kw for kw in offtopic_keywords if re.search(r'\b' + re.escape(kw) + r'\b', combined)]
            return {
                "is_relevant": False,
                "category": "offtopic",
                "confidence": 0.9,
                "reason": f"Contains keywords unrelated to database analysis: {found_keywords}",
                "message": (
                    "This request doesn't appear to be related to database query analysis.\n\n"
                    "This MCP is specifically designed for:\n"
                    "• Analyzing SQL query performance (Oracle & MySQL)\n"
                    "• Explaining execution plans and optimization\n"
                    "• Providing index and query recommendations\n"
                    "• Understanding database business logic\n\n"
                    "If you have a genuine database-related issue, please rephrase your request."
                )
            }

        if db_count >= 2:
            return {
                "is_relevant": True,
                "category": "relevant",
                "confidence": 0.8,
                "reason": "Contains database/query keywords",
                "message": None
            }

        if db_count == 1:
            return {
                "is_relevant": False,
                "category": "unclear",
                "confidence": 0.6,
                "reason": "Mentions databases but lacks context",
                "message": (
                    "I want to make sure this relates to database query analysis.\n\n"
                    "This MCP provides:\n"
                    "• SQL performance analysis and optimization\n"
                    "• Execution plan explanation\n"
                    "• Query optimization recommendations\n\n"
                    "Could you clarify how your request relates to these database capabilities?"
                )
            }

        # No database keywords at all
        return {
            "is_relevant": False,
            "category": "irrelevant",
            "confidence": 0.9,
            "reason": "No database or query-related keywords found",
            "message": (
                "This request doesn't mention database queries, SQL, or performance analysis.\n\n"
                "This MCP is specifically for database query optimization. If you need help with "
                "something else, this might not be the right tool.\n\n"
                "If you DO have a database-related issue, please include words like: query, SQL, "
                "database, performance, execution plan, index, etc."
            )
        }

    def generate_improvement_prompt(
        self,
        issue_type: str,
        title: str,
        description: str,
        quality_analysis: Dict
    ) -> str:
        """
        Generate prompt for LLM to improve unclear feedback.

        This prompt guides Claude on how to rewrite user feedback
        to be clearer and more actionable.
        """

        issues_section = ""
        if quality_analysis["issues_found"]:
            issues_list = "\n".join(f"- {issue}" for issue in quality_analysis["issues_found"])
            issues_section = f"\n**Issues detected:**\n{issues_list}\n"

        prompt = f"""Fix clarity issues in this feedback. Make MINIMAL changes.

**Type:** {issue_type}
**Title:** {title}
**Description:** {description}
**Quality Score:** {quality_analysis['quality_score']}/10
{issues_section}

**Guidelines:**
1. Make MINIMAL changes - preserve the user's brevity
2. Only fix vague/unclear parts (replace "it", "something", "doesn't work")
3. Keep it SHORT - don't expand unless absolutely necessary
4. NO boilerplate sections (no "Environment:", "Steps:", "Expected:" unless user implied them)
5. Preserve casual tone
6. Don't add bullet points unless user's meaning requires them

**Examples:**
- "bug in query" → "Bug: Query analysis fails for complex joins"
- "add feature" → "Feature request: Add [specific feature name]"
- Short input → Short output (don't expand)

**Output JSON:**
{{
  "improved_title": "Clearer title (SHORT)",
  "improved_description": "Clearer description (BRIEF - match user's length)",
  "changes_made": ["What you fixed"]
}}

NO text outside JSON."""

        return prompt

    def parse_improved_feedback(self, llm_response: str) -> Dict:
        """
        Parse LLM response to extract improved feedback.

        Args:
            llm_response: Raw response from LLM

        Returns:
            {
                "improved_title": str,
                "improved_description": str,
                "changes_made": [list],
                "error": str (if parsing failed)
            }
        """
        import json

        try:
            # Try to extract JSON from response
            # Handle cases where LLM adds markdown code blocks
            content = llm_response.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*\n', '', content)
                content = re.sub(r'\n```\s*$', '', content)

            # Parse JSON
            result = json.loads(content)

            # Validate required fields
            if "improved_title" not in result or "improved_description" not in result:
                return {
                    "error": "LLM response missing required fields",
                    "raw_response": llm_response
                }

            return {
                "improved_title": result["improved_title"],
                "improved_description": result["improved_description"],
                "changes_made": result.get("changes_made", []),
                "error": None
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "error": f"Could not parse LLM response as JSON: {str(e)}",
                "raw_response": llm_response
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing feedback: {e}")
            return {
                "error": f"Unexpected error: {str(e)}",
                "raw_response": llm_response
            }

    async def improve_feedback_with_llm(
        self,
        issue_type: str,
        title: str,
        description: str,
        quality_analysis: Dict
    ) -> Dict:
        """
        Use Claude API to actually improve the feedback.

        Returns:
            {
                "improved_title": str,
                "improved_description": str,
                "changes_made": [list],
                "error": str (if failed)
            }
        """
        try:
            import httpx
            import os

            # Get Claude API key
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return {"error": "ANTHROPIC_API_KEY not set - cannot improve feedback"}

            # Generate the improvement prompt
            prompt = self.generate_improvement_prompt(issue_type, title, description, quality_analysis)

            # Call Claude API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1024,
                        "messages": [{
                            "role": "user",
                            "content": prompt
                        }]
                    }
                )

                if response.status_code != 200:
                    return {"error": f"Claude API error: {response.status_code}"}

                result = response.json()
                llm_response = result["content"][0]["text"]

                # Parse the response
                return self.parse_improved_feedback(llm_response)

        except Exception as e:
            logger.error(f"Failed to improve feedback with LLM: {e}")
            return {"error": str(e)}


# Global instance
_quality_analyzer = FeedbackQualityAnalyzer()


def get_quality_analyzer() -> FeedbackQualityAnalyzer:
    """Get the global quality analyzer instance."""
    return _quality_analyzer


def quick_quality_check(issue_type: str, title: str, description: str) -> Tuple[bool, str, Dict]:
    """
    Quick quality check with user-friendly message.

    Returns:
        (is_good_quality, message, analysis_dict)
    """
    analyzer = get_quality_analyzer()
    analysis = analyzer.analyze_feedback_quality(issue_type, title, description)

    if not analysis["needs_improvement"]:
        return True, "✅ Feedback looks good!", analysis

    # Build friendly message
    score = analysis["quality_score"]
    issues = analysis["issues_found"]

    message = f"📊 **Quality Check:** {score}/10\n\n"

    if analysis["severity"] == "high":
        message += "⚠️ **Your feedback needs improvement:**\n"
    else:
        message += "💡 **Suggestions to improve your feedback:**\n"

    for issue in issues[:3]:  # Show max 3 issues
        message += f"• {issue}\n"

    if analysis["suggestions"]:
        message += f"\n**How to improve:**\n"
        for suggestion in analysis["suggestions"][:3]:
            message += f"• {suggestion}\n"

    message += f"\n💬 Would you like me to help rewrite this to be clearer?"

    return False, message, analysis
