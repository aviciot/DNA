"""
Interactive MCP Feedback System - Report bugs, request features, suggest improvements.

GENERIC MODULE: Copy to any MCP for GitHub issue management.
Configuration from settings.yaml - no code changes needed.
"""

import os
import logging
import traceback
from typing import Optional
import httpx
from mcp_app import mcp

logger = logging.getLogger(__name__)


def load_feedback_config():
    """Load feedback configuration from settings.yaml or environment."""
    try:
        import yaml
        with open("/app/config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)
            feedback_config = config.get("feedback", {})
            quality_config = feedback_config.get("quality", {})

            return {
                "enabled": feedback_config.get("enabled", True),
                "repo": feedback_config.get("repo", os.getenv("GITHUB_REPO", "owner/repo")),
                "maintainer": feedback_config.get("maintainer", "maintainer"),
                "github_token": os.getenv("GITHUB_TOKEN"),
                "safety": feedback_config.get("safety", {}),
                "quality": {
                    "enabled": quality_config.get("enabled", True),
                    "auto_improve": quality_config.get("auto_improve", True),
                    "auto_improve_threshold": quality_config.get("auto_improve_threshold", 4.0),
                    "good_quality_threshold": quality_config.get("good_quality_threshold", 7.0),
                    "min_quality_score": quality_config.get("min_quality_score", 0),
                },
            }
    except Exception as e:
        logger.warning(f"Could not load feedback config: {e}")
        return {
            "enabled": False,
            "repo": "owner/repo",
            "maintainer": "maintainer",
            "github_token": None,
            "safety": {},
            "quality": {
                "enabled": True,
                "auto_improve": True,
                "auto_improve_threshold": 4.0,
                "good_quality_threshold": 7.0,
                "min_quality_score": 0,
            },
        }


@mcp.tool(
    name="report_mcp_issue_interactive",
    description=(
        "🐛 Help user report bugs/features/improvements - BUT VALIDATE RELEVANCE FIRST.\n\n"
        "⚠️ CRITICAL - YOU MUST VALIDATE BEFORE CALLING THIS TOOL:\n"
        "This MCP is for DATABASE QUERY ANALYSIS - specifically:\n"
        "✅ SQL query performance analysis (Oracle & MySQL)\n"
        "✅ Execution plan optimization\n"
        "✅ Index recommendations\n"
        "✅ Query business logic explanation\n"
        "✅ Database metadata and caching\n\n"
        "❌ NOT for: Unrelated features, jokes, entertainment, non-database functionality\n\n"
        "🤔 YOUR JOB BEFORE CALLING THIS TOOL:\n"
        "1. ANALYZE: Does user's request relate to database query analysis?\n"
        "2. QUESTION: If unclear or absurd, ask user to clarify or explain MCP scope\n"
        "3. VALIDATE: Only call this tool if request is genuinely relevant\n"
        "4. PUSH BACK: Professionally decline if request is off-topic\n\n"
        "EXAMPLES:\n"
        "✅ ACCEPT: 'Query timeout on complex joins' → Relevant, call tool\n"
        "✅ ACCEPT: 'Add index recommendations' → Relevant, call tool\n"
        "❌ REJECT: 'Get lyrics with analysis' → Off-topic, explain MCP scope to user\n"
        "❌ REJECT: 'Order pizza when timeout' → Absurd, don't call tool\n\n"
        "**What happens when you DO call this tool:**\n"
        "• Rate limit check (3/hour, 10/day)\n"
        "• Quality analysis (clarity, completeness)\n"
        "• Preview before GitHub submission\n\n"
        "**Remember:** Your professional judgment BEFORE calling = Most important filter"
    ),
)
async def report_mcp_issue_interactive(
    issue_type: str,
    title: str,
    description: str,
    auto_submit: bool = False
):
    """
    Report an issue interactively with quality checking and preview.

    Args:
        issue_type: "bug", "feature", or "improvement"
        title: Short, clear title (5-200 chars)
        description: Detailed description (10-5000 chars)
        auto_submit: Skip preview and submit directly (default: False)

    Returns:
        Dict with status, quality analysis, preview, and submission result
    """
    logger.info("=" * 70)
    logger.info("🐛 TOOL CALLED: report_mcp_issue_interactive")
    logger.info(f"   Type: {issue_type}")
    logger.info(f"   Title: {title[:50]}...")
    logger.info(f"   Auto-submit: {auto_submit}")
    logger.info("=" * 70)

    try:
        # Load config
        config = load_feedback_config()

        if not config["enabled"]:
            return {
                "error": "Feedback system is not enabled",
                "message": "The feedback system is currently disabled. Please contact the maintainer directly."
            }

        if not config["github_token"]:
            return {
                "error": "GitHub token not configured",
                "message": "The maintainer needs to set GITHUB_TOKEN in .env to enable issue creation."
            }

        # Validate issue type
        valid_types = ["bug", "feature", "improvement"]
        if issue_type not in valid_types:
            return {
                "error": f"Invalid issue type: {issue_type}",
                "message": f"Please use one of: {', '.join(valid_types)}"
            }

        # Import safety and quality modules
        from tools.feedback_context import get_user_identifier, get_client_identifier, get_tracking_info
        from tools.feedback_safety_db import get_safety_manager
        from tools.feedback_quality import get_quality_analyzer, quick_quality_check

        # Get tracking info
        tracking = get_tracking_info()
        session_id = tracking["user_identifier"]
        client_id = tracking["client_identifier"]

        logger.info(f"📊 Session: {session_id[:30]}...")
        logger.info(f"🏢 Client: {client_id}")

        # STEP 1: Check rate limits
        safety = get_safety_manager()
        allowed, limit_msg = await safety.check_rate_limit(session_id, client_id)

        if not allowed:
            logger.warning(f"⏱️ Rate limit exceeded for {session_id[:20]}")
            return {
                "error": "Rate limit exceeded",
                "message": limit_msg,
                "stats": await safety.get_stats(session_id, client_id)
            }

        logger.info("✅ Rate limit check passed")

        # STEP 2: Validate content
        is_valid, validation_msg = safety.validate_content(title, description)

        if not is_valid:
            logger.warning(f"❌ Content validation failed")
            return {
                "error": "Content validation failed",
                "message": validation_msg
            }

        logger.info("✅ Content validation passed")

        # STEP 2.5: Relevance check (is this about database query analysis?)
        analyzer = get_quality_analyzer()
        relevance = analyzer.analyze_relevance_simple(issue_type, title, description)

        if not relevance["is_relevant"]:
            logger.warning(f"❌ Relevance check failed: {relevance['category']}")
            return {
                "error": "Not relevant to MCP",
                "category": relevance["category"],
                "reason": relevance["reason"],
                "message": relevance["message"]
            }

        logger.info(f"✅ Relevance check passed ({relevance['category']})")

        # STEP 3: Check for duplicates
        content = f"{title} {description}"
        is_duplicate, duplicate_msg = await safety.check_duplicate(session_id, content)

        if is_duplicate:
            logger.warning(f"🔄 Duplicate submission detected")
            return {
                "error": "Duplicate submission",
                "message": duplicate_msg
            }

        logger.info("✅ Duplicate check passed")

        # STEP 4: Quality analysis
        is_good, quality_msg, analysis = quick_quality_check(issue_type, title, description)

        logger.info(f"📊 Quality score: {analysis['quality_score']}/10")

        # Check minimum quality threshold
        min_score = config["quality"]["min_quality_score"]

        if analysis["quality_score"] < min_score:
            logger.warning(f"❌ Quality score {analysis['quality_score']} below minimum {min_score}")
            return {
                "error": "Quality too low",
                "message": (
                    f"⚠️ **Feedback Quality Too Low**\n\n"
                    f"Your feedback scored {analysis['quality_score']}/10, which is below the minimum threshold of {min_score}/10.\n\n"
                    f"**Issues found:**\n" + "\n".join(f"• {issue}" for issue in analysis["issues_found"]) + "\n\n"
                    f"**Please:**\n"
                    f"1. Use `improve_my_feedback` tool to get a better version\n"
                    f"2. Add more specific details about your issue\n"
                    f"3. Include examples, steps, or expected behavior\n\n"
                    f"We want to help, but need enough information to understand the problem!"
                ),
                "quality_analysis": analysis
            }

        # Get stats for tracking
        stats = await safety.get_stats(session_id, client_id)

        result = {
            "stage": "quality_check",
            "quality_analysis": {
                "score": analysis["quality_score"],
                "is_good": is_good,
                "message": quality_msg,
                "issues_found": analysis["issues_found"],
                "suggestions": analysis["suggestions"],
                "severity": analysis["severity"]
            },
            "original_feedback": {
                "type": issue_type,
                "title": title,
                "description": description
            },
            "tracking": {
                "session_id": tracking["session_id"],
                "submissions_remaining": stats
            }
        }

        # STEP 5: If quality is poor and not auto-submit, suggest improvement
        if not is_good and not auto_submit:
            logger.info("💡 Suggesting feedback improvement")
            result["stage"] = "needs_improvement"
            result["message"] = (
                f"{quality_msg}\n\n"
                f"**Options:**\n"
                f"1. Use `improve_my_feedback` tool to get a better version (recommended)\n"
                f"2. Edit your feedback and try again\n"
                f"3. Improve quality first, or confirm you want to submit as-is\n\n"
                f"To proceed without improvements, call this tool again with `auto_submit=True`\n"
                f"(Note: Very low quality submissions may still be flagged for review)"
            )
            return result

        # STEP 6: Create preview
        labels = [issue_type, "user-submitted"]

        # Add quality label (use thresholds from config)
        config = load_feedback_config()
        good_threshold = config["quality"]["good_quality_threshold"]
        improve_threshold = config["quality"]["auto_improve_threshold"]

        if analysis["quality_score"] >= good_threshold:
            labels.append("good-quality")
        elif analysis["quality_score"] < improve_threshold:
            labels.append("needs-clarification")

        issue_body = f"""{description}

---

**Issue Type:** {issue_type}
**Submitted via:** MCP Interactive Feedback
**Quality Score:** {analysis['quality_score']}/10
**Session ID:** {tracking['session_id'][:16]}...
"""

        preview = {
            "title": title,
            "body": issue_body,
            "labels": labels,
            "repo": config["repo"]
        }

        result["preview"] = preview

        # STEP 7: If auto-submit, create the issue
        if auto_submit:
            logger.info("🚀 Auto-submitting to GitHub...")

            try:
                github_result = await create_github_issue(
                    config["github_token"],
                    config["repo"],
                    title,
                    issue_body,
                    labels
                )

                if github_result.get("error"):
                    logger.error(f"❌ GitHub API error: {github_result['error']}")
                    return {
                        "error": "Failed to create GitHub issue",
                        "message": github_result["error"],
                        "preview": preview
                    }

                # Record submission to database
                await safety.record_submission(
                    session_identifier=session_id,
                    client_identifier=client_id,
                    submission_type=issue_type,
                    title=title,
                    description=description,
                    quality_score=analysis["quality_score"],
                    github_issue_number=github_result.get("number"),
                    github_issue_url=github_result.get("html_url")
                )

                logger.info(f"✅ Issue created: {github_result['html_url']}")

                result["stage"] = "submitted"
                result["github_issue"] = github_result
                stats = await safety.get_stats(session_id, client_id)
                result["message"] = (
                    f"✅ **Issue Created Successfully!**\n\n"
                    f"**Issue #{github_result['number']}:** {github_result['html_url']}\n\n"
                    f"Thank you for helping improve this MCP! 🎉\n\n"
                    f"**What's next:**\n"
                    f"• The maintainer ({config['maintainer']}) will review your submission\n"
                    f"• You can track progress at the link above\n"
                    f"• You can search existing issues with `search_mcp_issues`\n\n"
                    f"**Submissions remaining today:** {stats['session']['remaining_today']}"
                )

                return result

            except Exception as e:
                logger.exception("❌ Failed to create GitHub issue")
                return {
                    "error": "Submission failed",
                    "message": f"Could not create issue: {str(e)}",
                    "preview": preview,
                    "trace": traceback.format_exc()
                }

        # STEP 8: Return preview for manual confirmation
        logger.info("👀 Returning preview for user confirmation")
        result["stage"] = "preview"
        result["message"] = (
            f"📋 **Preview Your Issue**\n\n"
            f"**Title:** {title}\n"
            f"**Type:** {issue_type}\n"
            f"**Quality Score:** {analysis['quality_score']}/10\n"
            f"**Labels:** {', '.join(labels)}\n\n"
            f"**Description:**\n{description}\n\n"
            f"---\n\n"
            f"**To submit this issue:**\n"
            f"Call this tool again with `auto_submit=True`\n\n"
            f"**To improve the quality:**\n"
            f"Use `improve_my_feedback` tool first"
        )

        return result

    except Exception as e:
        logger.exception("❌ Exception in report_mcp_issue_interactive")
        return {
            "error": "Internal error",
            "message": f"An error occurred: {str(e)}",
            "trace": traceback.format_exc()
        }


@mcp.tool(
    name="improve_my_feedback",
    description=(
        "✨ Get help improving unclear or incomplete feedback.\n\n"
        "**What this does:**\n"
        "• Analyzes your original feedback\n"
        "• Rewrites it to be clearer and more specific\n"
        "• Preserves your original meaning\n"
        "• Shows what was improved\n\n"
        "**When to use:**\n"
        "• Your feedback scored low on quality check\n"
        "• English is not your first language\n"
        "• You want to make it more professional\n"
        "• You're not sure how to structure it\n\n"
        "**Usage:**\n"
        "Provide your original issue_type, title, and description.\n"
        "I'll generate an improved version you can review and use."
    ),
)
async def improve_my_feedback(
    issue_type: str,
    title: str,
    description: str
):
    """
    Use LLM to improve unclear feedback.

    Args:
        issue_type: "bug", "feature", or "improvement"
        title: Original title
        description: Original description

    Returns:
        Dict with improved version and explanation of changes
    """
    logger.info("✨ TOOL CALLED: improve_my_feedback")
    logger.info(f"   Type: {issue_type}")

    try:
        from tools.feedback_quality import get_quality_analyzer

        analyzer = get_quality_analyzer()

        # Analyze current quality
        analysis = analyzer.analyze_feedback_quality(issue_type, title, description)

        logger.info(f"📊 Current quality: {analysis['quality_score']}/10")

        # If already good quality, no improvement needed
        if not analysis["needs_improvement"]:
            return f"✅ Your feedback is already clear (score: {analysis['quality_score']}/10). No changes needed!"

        # Generate improvement prompt
        improvement_prompt = analyzer.generate_improvement_prompt(
            issue_type, title, description, analysis
        )

        # Actually improve the feedback using LLM
        improved = await analyzer.improve_feedback_with_llm(
            issue_type, title, description, analysis
        )

        if improved.get("error"):
            return f"❌ Could not improve feedback: {improved['error']}"

        # Return simple, clean response
        changes = "\n".join(f"• {change}" for change in improved.get("changes_made", []))

        return (
            f"✨ **Improved Version** (was {analysis['quality_score']}/10):\n\n"
            f"**Title:** {improved['improved_title']}\n\n"
            f"**Description:**\n{improved['improved_description']}\n\n"
            f"**Changes Made:**\n{changes}\n\n"
            f"💡 Copy this and use it with `report_mcp_issue_interactive`"
        )

    except Exception as e:
        logger.exception("❌ Exception in improve_my_feedback")
        return {
            "error": "Internal error",
            "message": f"Could not analyze feedback: {str(e)}",
            "trace": traceback.format_exc()
        }


@mcp.tool(
    name="search_mcp_issues",
    description=(
        "🔍 Search existing GitHub issues before creating a new one.\n\n"
        "**Why search first:**\n"
        "• Your issue might already be reported\n"
        "• You can add details to existing issues\n"
        "• Avoid duplicate submissions\n"
        "• See if there's a workaround\n\n"
        "**Search options:**\n"
        "• query: Keywords to search for\n"
        "• issue_type: Filter by bug/feature/improvement\n"
        "• state: open (default) or closed\n\n"
        "**Returns:**\n"
        "List of matching issues with title, status, and link."
    ),
)
async def search_mcp_issues(
    query: str,
    issue_type: Optional[str] = None,
    state: str = "open"
):
    """
    Search GitHub issues for this MCP.

    Args:
        query: Search keywords
        issue_type: Optional filter ("bug", "feature", "improvement")
        state: "open", "closed", or "all" (default: "open")

    Returns:
        List of matching issues
    """
    logger.info(f"🔍 TOOL CALLED: search_mcp_issues (query: {query})")

    try:
        config = load_feedback_config()

        if not config["enabled"]:
            return {
                "error": "Feedback system is not enabled",
                "issues": []
            }

        # Build search query
        search_terms = [f"repo:{config['repo']}", f"is:issue", f"is:{state}"]

        if issue_type:
            search_terms.append(f"label:{issue_type}")

        search_terms.append(query)

        search_query = " ".join(search_terms)

        logger.info(f"   GitHub search: {search_query}")

        # Search GitHub
        results = await search_github_issues(config["github_token"], search_query)

        if results.get("error"):
            return {
                "error": results["error"],
                "issues": []
            }

        issues = results.get("items", [])

        logger.info(f"   Found {len(issues)} issues")

        # Format results
        formatted = []
        for issue in issues[:10]:  # Limit to 10 results
            formatted.append({
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "labels": [label["name"] for label in issue.get("labels", [])],
                "url": issue["html_url"],
                "created_at": issue["created_at"],
                "comments": issue.get("comments", 0)
            })

        message = f"🔍 **Found {len(issues)} issue(s)**\n\n"

        if formatted:
            for issue in formatted[:5]:  # Show first 5 in message
                message += f"**#{issue['number']}** [{issue['state']}] {issue['title']}\n"
                message += f"   {issue['url']}\n"
                message += f"   Labels: {', '.join(issue['labels'])}\n\n"

            if len(formatted) > 5:
                message += f"... and {len(formatted) - 5} more (see `issues` field)\n"
        else:
            message += "No matching issues found. Your issue might be new!\n"

        return {
            "count": len(issues),
            "issues": formatted,
            "message": message,
            "search_query": search_query
        }

    except Exception as e:
        logger.exception("❌ Exception in search_mcp_issues")
        return {
            "error": "Search failed",
            "message": f"Could not search issues: {str(e)}",
            "issues": [],
            "trace": traceback.format_exc()
        }


# GitHub API helper functions

async def create_github_issue(token: str, repo: str, title: str, body: str, labels: list) -> dict:
    """Create a GitHub issue using the REST API."""

    url = f"https://api.github.com/repos/{repo}/issues"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    data = {
        "title": title,
        "body": body,
        "labels": labels
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers, timeout=30.0)

            if response.status_code == 201:
                issue_data = response.json()
                return {
                    "number": issue_data["number"],
                    "html_url": issue_data["html_url"],
                    "state": issue_data["state"],
                    "created_at": issue_data["created_at"]
                }
            else:
                return {
                    "error": f"GitHub API returned {response.status_code}: {response.text}"
                }

    except Exception as e:
        logger.exception("Failed to create GitHub issue")
        return {
            "error": f"HTTP request failed: {str(e)}"
        }


async def search_github_issues(token: str, query: str) -> dict:
    """Search GitHub issues using the Search API."""

    url = "https://api.github.com/search/issues"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 10
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=30.0)

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"GitHub API returned {response.status_code}: {response.text}",
                    "items": []
                }

    except Exception as e:
        logger.exception("Failed to search GitHub issues")
        return {
            "error": f"HTTP request failed: {str(e)}",
            "items": []
        }
