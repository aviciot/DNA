"""
Admin-only feedback management tools.

SECURITY: These tools require "admin" API key access.
Only users authenticated with the "admin" key can use these tools.
"""

import logging
from typing import Optional
from mcp_app import mcp

logger = logging.getLogger(__name__)


def check_admin_access() -> tuple[bool, str]:
    """
    Check if current user has admin access.

    Returns:
        (is_admin, error_message)
    """
    try:
        from tools.feedback_context import get_tracking_info

        tracking = get_tracking_info()
        client_id = tracking.get("client_id", "")

        # Check if user is admin
        if client_id.lower() != "admin":
            logger.warning(f"🚫 Non-admin user '{client_id}' attempted to access admin tool")
            return False, "ACCESS_DENIED_ADMIN_ONLY"

        logger.info(f"✅ Admin access granted to user: {client_id}")
        return True, ""

    except Exception as e:
        logger.error(f"Error checking admin access: {e}")
        return False, "ACCESS_DENIED_ADMIN_ONLY"


@mcp.tool(
    name="get_feedback_dashboard",
    description="🔒 [ADMIN ONLY] View feedback dashboard with statistics, submissions, and blocked users. Requires admin API key.",
)
async def get_feedback_dashboard(
    limit: int = 20,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None
):
    """
    Get comprehensive feedback dashboard (admin only).

    Args:
        limit: Maximum number of recent submissions to return (default: 20)
        status_filter: Filter by status (submitted, created, failed)
        type_filter: Filter by type (bug, feature, improvement)

    Returns:
        Dashboard with stats and recent submissions
    """
    logger.info("=" * 70)
    logger.info("📊 TOOL CALLED: get_feedback_dashboard (ADMIN)")
    logger.info(f"   Limit: {limit}, Status: {status_filter}, Type: {type_filter}")
    logger.info("=" * 70)

    # Check admin access
    is_admin, error_msg = check_admin_access()
    if not is_admin:
        return "🔒 Access denied. Admin access required."

    try:
        # Check if database is available
        from knowledge_db import get_knowledge_db
        db = get_knowledge_db()

        if not db or not db.pool:
            return {
                "error": "database_unavailable",
                "message": "Database connection not available. System may be using in-memory storage.",
                "note": "Admin dashboard requires database storage to be enabled."
            }

        async with db.pool.acquire() as conn:
            # Get overall statistics
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_submissions,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    COUNT(DISTINCT client_id) as unique_clients,
                    ROUND(AVG(quality_score), 1) as avg_quality_score,
                    COUNT(*) FILTER (WHERE submission_type = 'bug') as bug_count,
                    COUNT(*) FILTER (WHERE submission_type = 'feature') as feature_count,
                    COUNT(*) FILTER (WHERE submission_type = 'improvement') as improvement_count,
                    COUNT(*) FILTER (WHERE status = 'created') as successfully_created,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_submissions,
                    COUNT(*) FILTER (WHERE status = 'submitted') as pending_submissions
                FROM mcp_performance.feedback_submissions
            """)

            # Build query for recent submissions
            where_clauses = []
            params = []
            param_count = 1

            if status_filter:
                where_clauses.append(f"status = ${param_count}")
                params.append(status_filter)
                param_count += 1

            if type_filter:
                where_clauses.append(f"submission_type = ${param_count}")
                params.append(type_filter)
                param_count += 1

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get recent submissions
            recent_query = f"""
                SELECT
                    id,
                    session_id,
                    client_id,
                    submission_type,
                    title,
                    SUBSTRING(description, 1, 200) as description_preview,
                    quality_score,
                    github_issue_number,
                    github_issue_url,
                    status,
                    created_at
                FROM mcp_performance.feedback_submissions
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """
            params.append(limit)

            recent_submissions = await conn.fetch(recent_query, *params)

            # Get blocked sessions/clients
            blocked = await conn.fetch("""
                SELECT
                    identifier,
                    identifier_type,
                    blocked_at,
                    unblock_at,
                    EXTRACT(EPOCH FROM (unblock_at - NOW()))/3600 as hours_remaining,
                    reason
                FROM mcp_performance.feedback_blocked_sessions
                WHERE unblock_at > NOW()
                ORDER BY blocked_at DESC
            """)

            # Get top contributors
            top_contributors = await conn.fetch("""
                SELECT
                    client_id,
                    COUNT(*) as submission_count,
                    ROUND(AVG(quality_score), 1) as avg_quality,
                    MAX(created_at) as last_submission
                FROM mcp_performance.feedback_submissions
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY client_id
                ORDER BY submission_count DESC
                LIMIT 10
            """)

            # Format response
            dashboard = {
                "summary": {
                    "total_submissions": stats["total_submissions"],
                    "last_24_hours": stats["last_24h"],
                    "last_hour": stats["last_hour"],
                    "unique_sessions": stats["unique_sessions"],
                    "unique_clients": stats["unique_clients"],
                    "average_quality_score": float(stats["avg_quality_score"]) if stats["avg_quality_score"] else 0.0
                },
                "by_type": {
                    "bugs": stats["bug_count"],
                    "features": stats["feature_count"],
                    "improvements": stats["improvement_count"]
                },
                "by_status": {
                    "successfully_created": stats["successfully_created"],
                    "failed": stats["failed_submissions"],
                    "pending": stats["pending_submissions"]
                },
                "recent_submissions": [
                    {
                        "id": row["id"],
                        "session_id": row["session_id"][:16] + "...",
                        "client_id": row["client_id"],
                        "type": row["submission_type"],
                        "title": row["title"],
                        "description_preview": row["description_preview"] + ("..." if len(row["description_preview"]) >= 200 else ""),
                        "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
                        "github_issue": f"#{row['github_issue_number']}" if row["github_issue_number"] else None,
                        "github_url": row["github_issue_url"],
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat()
                    }
                    for row in recent_submissions
                ],
                "blocked_users": [
                    {
                        "identifier": row["identifier"][:20] + "..." if len(row["identifier"]) > 20 else row["identifier"],
                        "type": row["identifier_type"],
                        "blocked_at": row["blocked_at"].isoformat(),
                        "hours_remaining": round(row["hours_remaining"], 1),
                        "reason": row["reason"]
                    }
                    for row in blocked
                ],
                "top_contributors": [
                    {
                        "client_id": row["client_id"],
                        "submissions": row["submission_count"],
                        "avg_quality": float(row["avg_quality"]) if row["avg_quality"] else None,
                        "last_submission": row["last_submission"].isoformat()
                    }
                    for row in top_contributors
                ]
            }

            # Build summary message
            message = f"""📊 **Feedback System Dashboard**

**📈 Summary:**
• Total submissions: {dashboard['summary']['total_submissions']}
• Last 24 hours: {dashboard['summary']['last_24_hours']}
• Last hour: {dashboard['summary']['last_hour']}
• Unique users: {dashboard['summary']['unique_sessions']}
• Unique teams: {dashboard['summary']['unique_clients']}
• Avg quality score: {dashboard['summary']['average_quality_score']}/10

**🐛 By Type:**
• Bugs: {dashboard['by_type']['bugs']}
• Features: {dashboard['by_type']['features']}
• Improvements: {dashboard['by_type']['improvements']}

**✅ By Status:**
• Created on GitHub: {dashboard['by_status']['successfully_created']}
• Failed: {dashboard['by_status']['failed']}
• Pending: {dashboard['by_status']['pending']}

**📋 Recent Submissions:** {len(dashboard['recent_submissions'])} shown (limit: {limit})
"""

            if dashboard['blocked_users']:
                message += f"\n**🚫 Blocked Users:** {len(dashboard['blocked_users'])} currently blocked"

            if dashboard['top_contributors']:
                message += f"\n**🏆 Top Contributors:** {len(dashboard['top_contributors'])} active in last 30 days"

            dashboard["message"] = message

            logger.info(f"✅ Dashboard retrieved: {stats['total_submissions']} total submissions")
            return dashboard

    except Exception as e:
        logger.exception("❌ Exception in get_feedback_dashboard")
        return {
            "error": "internal_error",
            "message": f"Failed to retrieve dashboard: {str(e)}"
        }


@mcp.tool(
    name="get_github_issues_summary",
    description="🔒 [ADMIN ONLY] Get summary of GitHub issues created from feedback (total, by type, success rate). Requires admin API key.",
)
async def get_github_issues_summary(
    include_failed: bool = False,
    limit: int = 10
):
    """
    Get summary of GitHub issues (admin only).

    Args:
        include_failed: Include failed submissions (default: False)
        limit: Maximum number of recent issues to return (default: 10)

    Returns:
        Summary of GitHub issues created from feedback
    """
    logger.info("📊 TOOL CALLED: get_github_issues_summary (ADMIN)")

    # Check admin access
    is_admin, error_msg = check_admin_access()
    if not is_admin:
        return "🔒 Access denied. Admin access required."

    try:
        from knowledge_db import get_knowledge_db
        db = get_knowledge_db()

        if not db or not db.pool:
            return {
                "error": "database_unavailable",
                "message": "Database connection not available."
            }

        async with db.pool.acquire() as conn:
            # Get GitHub issues stats
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE github_issue_number IS NOT NULL) as total_created,
                    COUNT(*) FILTER (WHERE github_issue_number IS NOT NULL AND submission_type = 'bug') as bugs,
                    COUNT(*) FILTER (WHERE github_issue_number IS NOT NULL AND submission_type = 'feature') as features,
                    COUNT(*) FILTER (WHERE github_issue_number IS NOT NULL AND submission_type = 'improvement') as improvements,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(*) FILTER (WHERE status = 'submitted') as pending
                FROM mcp_performance.feedback_submissions
            """)

            # Get recent GitHub issues
            status_filter = "status IN ('created', 'failed')" if include_failed else "status = 'created'"

            recent_issues = await conn.fetch(f"""
                SELECT
                    id,
                    submission_type,
                    title,
                    github_issue_number,
                    github_issue_url,
                    quality_score,
                    status,
                    created_at
                FROM mcp_performance.feedback_submissions
                WHERE {status_filter}
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)

            # Format response
            summary = {
                "totals": {
                    "created_on_github": stats["total_created"],
                    "bugs": stats["bugs"],
                    "features": stats["features"],
                    "improvements": stats["improvements"],
                    "failed": stats["failed"],
                    "pending": stats["pending"]
                },
                "success_rate": round(
                    (stats["total_created"] / (stats["total_created"] + stats["failed"]) * 100)
                    if (stats["total_created"] + stats["failed"]) > 0 else 0,
                    1
                ),
                "recent_issues": [
                    {
                        "id": row["id"],
                        "type": row["submission_type"],
                        "title": row["title"],
                        "github_issue": f"#{row['github_issue_number']}" if row["github_issue_number"] else "N/A",
                        "github_url": row["github_issue_url"] or "N/A",
                        "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat()
                    }
                    for row in recent_issues
                ]
            }

            message = f"""🐛 **GitHub Issues Summary**

**📊 Total Issues Created:** {summary['totals']['created_on_github']}

**By Type:**
• 🐛 Bugs: {summary['totals']['bugs']}
• ✨ Features: {summary['totals']['features']}
• 🔧 Improvements: {summary['totals']['improvements']}

**Status:**
• ✅ Success rate: {summary['success_rate']}%
• ❌ Failed: {summary['totals']['failed']}
• ⏳ Pending: {summary['totals']['pending']}

**Recent Issues:** {len(summary['recent_issues'])} shown (limit: {limit})
"""

            if summary['recent_issues']:
                message += "\n**Latest Issues:**\n"
                for issue in summary['recent_issues'][:5]:
                    status_emoji = "✅" if issue['status'] == 'created' else "❌"
                    message += f"{status_emoji} {issue['github_issue']} - {issue['title'][:50]}...\n"
                    if issue['github_url'] != "N/A":
                        message += f"   {issue['github_url']}\n"

            summary["message"] = message

            logger.info(f"✅ GitHub issues summary: {stats['total_created']} created")
            return summary

    except Exception as e:
        logger.exception("❌ Exception in get_github_issues_summary")
        return {
            "error": "internal_error",
            "message": f"Failed to retrieve GitHub issues: {str(e)}"
        }


@mcp.tool(
    name="get_feedback_by_client",
    description="🔒 [ADMIN ONLY] View feedback submissions by client/team (stats, rate limits, block status). Requires admin API key.",
)
async def get_feedback_by_client(
    client_id: str,
    limit: int = 20
):
    """
    Get feedback submissions by client/team (admin only).

    Args:
        client_id: Client/team identifier
        limit: Maximum submissions to return

    Returns:
        Client's submissions and statistics
    """
    logger.info(f"📊 TOOL CALLED: get_feedback_by_client (ADMIN) - Client: {client_id}")

    # Check admin access
    is_admin, error_msg = check_admin_access()
    if not is_admin:
        return "🔒 Access denied. Admin access required."

    try:
        from knowledge_db import get_knowledge_db
        db = get_knowledge_db()

        if not db or not db.pool:
            return {
                "error": "database_unavailable",
                "message": "Database connection not available."
            }

        async with db.pool.acquire() as conn:
            # Get client stats
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_submissions,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
                    ROUND(AVG(quality_score), 1) as avg_quality,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    MIN(created_at) as first_submission,
                    MAX(created_at) as last_submission
                FROM mcp_performance.feedback_submissions
                WHERE client_id = $1
            """, client_id)

            # Check if blocked
            blocked = await conn.fetchrow("""
                SELECT
                    unblock_at,
                    reason,
                    EXTRACT(EPOCH FROM (unblock_at - NOW()))/3600 as hours_remaining
                FROM mcp_performance.feedback_blocked_sessions
                WHERE identifier = $1 AND identifier_type = 'client' AND unblock_at > NOW()
            """, client_id)

            # Get submissions
            submissions = await conn.fetch("""
                SELECT
                    id,
                    session_id,
                    submission_type,
                    title,
                    quality_score,
                    github_issue_number,
                    status,
                    created_at
                FROM mcp_performance.feedback_submissions
                WHERE client_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, client_id, limit)

            result = {
                "client_id": client_id,
                "statistics": {
                    "total_submissions": stats["total_submissions"],
                    "last_24_hours": stats["last_24h"],
                    "last_hour": stats["last_hour"],
                    "average_quality": float(stats["avg_quality"]) if stats["avg_quality"] else 0.0,
                    "unique_sessions": stats["unique_sessions"],
                    "first_submission": stats["first_submission"].isoformat() if stats["first_submission"] else None,
                    "last_submission": stats["last_submission"].isoformat() if stats["last_submission"] else None
                },
                "is_blocked": blocked is not None,
                "block_info": {
                    "hours_remaining": round(blocked["hours_remaining"], 1),
                    "reason": blocked["reason"],
                    "unblock_at": blocked["unblock_at"].isoformat()
                } if blocked else None,
                "submissions": [
                    {
                        "id": row["id"],
                        "session_id": row["session_id"][:16] + "...",
                        "type": row["submission_type"],
                        "title": row["title"],
                        "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
                        "github_issue": f"#{row['github_issue_number']}" if row["github_issue_number"] else None,
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat()
                    }
                    for row in submissions
                ]
            }

            message = f"""👥 **Client Feedback Report: {client_id}**

**📊 Statistics:**
• Total submissions: {result['statistics']['total_submissions']}
• Last 24 hours: {result['statistics']['last_24_hours']}
• Last hour: {result['statistics']['last_hour']}
• Average quality: {result['statistics']['average_quality']}/10
• Unique sessions: {result['statistics']['unique_sessions']}

**⏱️ Activity:**
• First submission: {result['statistics']['first_submission'] or 'N/A'}
• Last submission: {result['statistics']['last_submission'] or 'N/A'}

**🚫 Block Status:** {"BLOCKED" if result['is_blocked'] else "Active"}
"""

            if result['is_blocked']:
                message += f"• Time remaining: {result['block_info']['hours_remaining']} hours\n"
                message += f"• Reason: {result['block_info']['reason']}\n"

            message += f"\n**Recent Submissions:** {len(result['submissions'])} shown (limit: {limit})"

            result["message"] = message

            logger.info(f"✅ Client report: {stats['total_submissions']} submissions")
            return result

    except Exception as e:
        logger.exception("❌ Exception in get_feedback_by_client")
        return {
            "error": "internal_error",
            "message": f"Failed to retrieve client feedback: {str(e)}"
        }
