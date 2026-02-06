"""
Database-backed safety layer for MCP feedback system.

Provides persistent rate limiting across server restarts.
Falls back to in-memory if database is unavailable.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FeedbackSafetyManagerDB:
    """
    Database-backed rate limiting and validation.
    Stores data in PostgreSQL for persistence.
    """

    def __init__(self, db_pool=None):
        """
        Initialize with optional database connection pool.

        Args:
            db_pool: asyncpg connection pool (optional)
        """
        self.db_pool = db_pool
        self.use_db = db_pool is not None

        # In-memory fallback (if DB unavailable)
        self._session_submissions: Dict[str, List[datetime]] = {}
        self._session_hashes: Dict[str, datetime] = {}
        self._blocked_sessions: Dict[str, datetime] = {}
        self._client_submissions: Dict[str, List[datetime]] = {}
        self._blocked_clients: Dict[str, datetime] = {}

        # Configuration
        self.session_max_per_hour = 3
        self.session_max_per_day = 10
        self.client_max_per_hour = 20
        self.client_max_per_day = 50
        self.duplicate_window_minutes = 30
        self.block_duration_hours = 24
        self.max_description_length = 5000
        self.max_title_length = 200

        if self.use_db:
            logger.info("✅ Feedback safety using PostgreSQL for persistent storage")
        else:
            logger.warning("⚠️  Feedback safety using in-memory storage (data lost on restart)")

    async def check_rate_limit(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Check rate limits using database or in-memory."""

        if self.use_db:
            return await self._check_rate_limit_db(session_identifier, client_identifier)
        else:
            return self._check_rate_limit_memory(session_identifier, client_identifier)

    async def _check_rate_limit_db(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Check rate limits using PostgreSQL."""

        try:
            async with self.db_pool.acquire() as conn:
                now = datetime.now()

                # Check if session is blocked
                blocked_session = await conn.fetchrow("""
                    SELECT unblock_at FROM mcp_performance.feedback_blocked_sessions
                    WHERE identifier = $1 AND identifier_type = 'session' AND unblock_at > $2
                """, session_identifier, now)

                if blocked_session:
                    unblock_at = blocked_session['unblock_at']
                    hours_left = int((unblock_at - now).total_seconds() / 3600)
                    return False, (
                        f"⛔ **You are temporarily blocked**\n\n"
                        f"Reason: Rate limit exceeded\n"
                        f"Time remaining: ~{hours_left} hours\n\n"
                        f"This helps maintain quality and prevent spam."
                    )

                # Check if client is blocked
                if client_identifier:
                    blocked_client = await conn.fetchrow("""
                        SELECT unblock_at FROM mcp_performance.feedback_blocked_sessions
                        WHERE identifier = $1 AND identifier_type = 'client' AND unblock_at > $2
                    """, client_identifier, now)

                    if blocked_client:
                        unblock_at = blocked_client['unblock_at']
                        hours_left = int((unblock_at - now).total_seconds() / 3600)
                        return False, (
                            f"⛔ **Your team/organization is temporarily blocked**\n\n"
                            f"Reason: Team rate limit exceeded\n"
                            f"Time remaining: ~{hours_left} hours\n\n"
                            f"Please coordinate with your team to manage feedback submissions."
                        )

                # Check session hourly limit
                one_hour_ago = now - timedelta(hours=1)
                session_last_hour = await conn.fetchval("""
                    SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND created_at > $2
                """, session_identifier, one_hour_ago)

                if session_last_hour >= self.session_max_per_hour:
                    # Get oldest submission in last hour
                    oldest = await conn.fetchval("""
                        SELECT created_at FROM mcp_performance.feedback_submissions
                        WHERE session_id = $1 AND created_at > $2
                        ORDER BY created_at ASC LIMIT 1
                    """, session_identifier, one_hour_ago)

                    if oldest:
                        minutes_wait = 60 - int((now - oldest).total_seconds() / 60)
                        return False, (
                            f"⏱️ **Hourly Rate Limit Reached**\n\n"
                            f"Your limit: {self.session_max_per_hour} submissions per hour\n"
                            f"Wait time: {minutes_wait} minutes\n\n"
                            f"💡 **Tip:** Search existing issues first!\n"
                            f"Say: 'Search issues about [topic]'"
                        )

                # Check session daily limit
                one_day_ago = now - timedelta(days=1)
                session_last_day = await conn.fetchval("""
                    SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND created_at > $2
                """, session_identifier, one_day_ago)

                if session_last_day >= self.session_max_per_day:
                    return False, (
                        f"📊 **Daily Limit Reached**\n\n"
                        f"Your limit: {self.session_max_per_day} submissions per day\n"
                        f"Current: {session_last_day} submissions today\n\n"
                        f"You can submit more feedback tomorrow!"
                    )

                # Check client limits
                if client_identifier and self.client_max_per_hour:
                    client_last_hour = await conn.fetchval("""
                        SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                        WHERE client_id = $1 AND created_at > $2
                    """, client_identifier, one_hour_ago)

                    if client_last_hour >= self.client_max_per_hour:
                        oldest = await conn.fetchval("""
                            SELECT created_at FROM mcp_performance.feedback_submissions
                            WHERE client_id = $1 AND created_at > $2
                            ORDER BY created_at ASC LIMIT 1
                        """, client_identifier, one_hour_ago)

                        if oldest:
                            minutes_wait = 60 - int((now - oldest).total_seconds() / 60)
                            return False, (
                                f"🏢 **Team Hourly Limit Reached**\n\n"
                                f"Team limit: {self.client_max_per_hour} submissions per hour\n"
                                f"Current: {client_last_hour} by your team this hour\n"
                                f"Wait time: {minutes_wait} minutes\n\n"
                                f"💡 **Tip:** Coordinate with your team to avoid hitting team limits."
                            )

                    if self.client_max_per_day:
                        client_last_day = await conn.fetchval("""
                            SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                            WHERE client_id = $1 AND created_at > $2
                        """, client_identifier, one_day_ago)

                        if client_last_day >= self.client_max_per_day:
                            return False, (
                                f"🏢 **Team Daily Limit Reached**\n\n"
                                f"Team limit: {self.client_max_per_day} submissions per day\n"
                                f"Current: {client_last_day} submissions by your team today\n\n"
                                f"Your team can submit more feedback tomorrow."
                            )

                return True, ""

        except Exception as e:
            logger.error(f"Database error in rate limit check, falling back to in-memory: {e}")
            return self._check_rate_limit_memory(session_identifier, client_identifier)

    def _check_rate_limit_memory(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> Tuple[bool, str]:
        """In-memory rate limit check (fallback)."""

        now = datetime.now()

        # Check session block
        if session_identifier in self._blocked_sessions:
            unblock_at = self._blocked_sessions[session_identifier]
            if now < unblock_at:
                hours_left = int((unblock_at - now).total_seconds() / 3600)
                return False, (
                    f"⛔ **You are temporarily blocked**\n\n"
                    f"Reason: Rate limit exceeded\n"
                    f"Time remaining: ~{hours_left} hours"
                )
            else:
                del self._blocked_sessions[session_identifier]

        # Check client block
        if client_identifier and client_identifier in self._blocked_clients:
            unblock_at = self._blocked_clients[client_identifier]
            if now < unblock_at:
                hours_left = int((unblock_at - now).total_seconds() / 3600)
                return False, (
                    f"⛔ **Your team is temporarily blocked**\n\n"
                    f"Time remaining: ~{hours_left} hours"
                )
            else:
                del self._blocked_clients[client_identifier]

        # Initialize tracking
        if session_identifier not in self._session_submissions:
            self._session_submissions[session_identifier] = []

        # Clean old submissions
        self._session_submissions[session_identifier] = [
            ts for ts in self._session_submissions[session_identifier]
            if now - ts < timedelta(days=1)
        ]

        session_subs = self._session_submissions[session_identifier]

        # Check hourly limit
        session_last_hour = [ts for ts in session_subs if now - ts < timedelta(hours=1)]
        if len(session_last_hour) >= self.session_max_per_hour:
            minutes_wait = 60 - int((now - session_last_hour[0]).total_seconds() / 60)
            return False, (
                f"⏱️ **Hourly Rate Limit Reached**\n\n"
                f"Your limit: {self.session_max_per_hour} submissions per hour\n"
                f"Wait time: {minutes_wait} minutes"
            )

        # Check daily limit
        if len(session_subs) >= self.session_max_per_day:
            return False, (
                f"📊 **Daily Limit Reached**\n\n"
                f"Your limit: {self.session_max_per_day} submissions per day"
            )

        return True, ""

    async def check_duplicate(self, session_identifier: str, content: str) -> Tuple[bool, str]:
        """Check for duplicate submissions."""

        content_hash = hashlib.md5(content.lower().encode()).hexdigest()

        if self.use_db:
            return await self._check_duplicate_db(session_identifier, content_hash)
        else:
            return self._check_duplicate_memory(session_identifier, content_hash)

    async def _check_duplicate_db(self, session_identifier: str, content_hash: str) -> Tuple[bool, str]:
        """Check duplicates using database."""

        try:
            async with self.db_pool.acquire() as conn:
                window_start = datetime.now() - timedelta(minutes=self.duplicate_window_minutes)

                duplicate = await conn.fetchrow("""
                    SELECT created_at FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND content_hash = $2 AND created_at > $3
                    ORDER BY created_at DESC LIMIT 1
                """, session_identifier, content_hash, window_start)

                if duplicate:
                    submitted_at = duplicate['created_at']
                    time_since = datetime.now() - submitted_at
                    minutes_ago = int(time_since.total_seconds() / 60)
                    minutes_left = self.duplicate_window_minutes - minutes_ago

                    return True, (
                        f"🔄 **Duplicate Submission**\n\n"
                        f"You submitted identical feedback {minutes_ago} minute(s) ago.\n"
                        f"Wait time: {minutes_left} minutes"
                    )

                return False, ""

        except Exception as e:
            logger.error(f"Database error in duplicate check, falling back: {e}")
            return self._check_duplicate_memory(session_identifier, content_hash)

    def _check_duplicate_memory(self, session_identifier: str, content_hash: str) -> Tuple[bool, str]:
        """In-memory duplicate check."""

        key = f"{session_identifier}:{content_hash}"

        if key in self._session_hashes:
            submitted_at = self._session_hashes[key]
            time_since = datetime.now() - submitted_at

            if time_since < timedelta(minutes=self.duplicate_window_minutes):
                minutes_ago = int(time_since.total_seconds() / 60)
                minutes_left = self.duplicate_window_minutes - minutes_ago

                return True, (
                    f"🔄 **Duplicate Submission**\n\n"
                    f"You submitted identical feedback {minutes_ago} minute(s) ago.\n"
                    f"Wait time: {minutes_left} minutes"
                )

        return False, ""

    def validate_content(self, title: str, description: str) -> Tuple[bool, str]:
        """Validate content (same for both DB and memory)."""

        # Check lengths
        if len(title) > self.max_title_length:
            return False, (
                f"❌ **Title Too Long**\n\n"
                f"Maximum: {self.max_title_length} characters\n"
                f"Current: {len(title)} characters"
            )

        if len(title) < 5:
            return False, (
                "❌ **Title Too Short**\n\n"
                "Minimum: 5 characters"
            )

        if len(description) > self.max_description_length:
            return False, (
                f"❌ **Description Too Long**\n\n"
                f"Maximum: {self.max_description_length} characters\n"
                f"Current: {len(description)} characters"
            )

        if len(description) < 10:
            return False, (
                "❌ **Description Too Short**\n\n"
                "Minimum: 10 characters"
            )

        # Check for spam patterns
        spam_patterns = [
            (r'(.)\\1{20,}', "repeated characters"),
            (r'http[s]?://(?!github\\.com)', "external links (only github.com allowed)"),
            (r'\\b(buy|sell|click here|subscribe|download now)\\b', "promotional content"),
            (r'[A-Z]{50,}', "excessive caps"),
        ]

        combined = f"{title} {description}".lower()

        for pattern, reason in spam_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return False, (
                    f"⚠️ **Potential Spam Detected**\n\n"
                    f"Issue: {reason}"
                )

        return True, ""

    async def record_submission(
        self,
        session_identifier: str,
        client_identifier: Optional[str],
        submission_type: str,
        title: str,
        description: str,
        quality_score: Optional[float] = None,
        github_issue_number: Optional[int] = None,
        github_issue_url: Optional[str] = None
    ):
        """Record submission to database or memory."""

        content = f"{title} {description}"
        content_hash = hashlib.md5(content.lower().encode()).hexdigest()

        if self.use_db:
            await self._record_submission_db(
                session_identifier, client_identifier, submission_type,
                title, description, content_hash, quality_score,
                github_issue_number, github_issue_url
            )
        else:
            self._record_submission_memory(session_identifier, client_identifier, content_hash)

    async def _record_submission_db(
        self,
        session_identifier: str,
        client_identifier: Optional[str],
        submission_type: str,
        title: str,
        description: str,
        content_hash: str,
        quality_score: Optional[float],
        github_issue_number: Optional[int],
        github_issue_url: Optional[str]
    ):
        """Record to PostgreSQL."""

        try:
            async with self.db_pool.acquire() as conn:
                status = 'created' if github_issue_number else 'submitted'

                await conn.execute("""
                    INSERT INTO mcp_performance.feedback_submissions
                    (session_id, client_id, submission_type, title, description,
                     content_hash, quality_score, github_issue_number, github_issue_url, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, session_identifier, client_identifier or 'unknown',
                submission_type, title, description, content_hash,
                quality_score, github_issue_number, github_issue_url, status)

                # Check for abuse and auto-block
                one_hour_ago = datetime.now() - timedelta(hours=1)
                recent_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND created_at > $2
                """, session_identifier, one_hour_ago)

                if recent_count >= self.session_max_per_hour * 2:
                    unblock_at = datetime.now() + timedelta(hours=self.block_duration_hours)
                    await conn.execute("""
                        INSERT INTO mcp_performance.feedback_blocked_sessions
                        (identifier, identifier_type, unblock_at, reason)
                        VALUES ($1, 'session', $2, 'Automatic block: Rate limit abuse')
                        ON CONFLICT (identifier) DO UPDATE SET unblock_at = $2
                    """, session_identifier, unblock_at)
                    logger.warning(f"🚫 Auto-blocked session: {session_identifier[:30]}")

        except Exception as e:
            logger.error(f"Failed to record submission to database: {e}")
            self._record_submission_memory(session_identifier, client_identifier, content_hash)

    def _record_submission_memory(self, session_identifier: str, client_identifier: Optional[str], content_hash: str):
        """Record to memory."""

        now = datetime.now()

        if session_identifier not in self._session_submissions:
            self._session_submissions[session_identifier] = []
        self._session_submissions[session_identifier].append(now)

        key = f"{session_identifier}:{content_hash}"
        self._session_hashes[key] = now

        if client_identifier:
            if client_identifier not in self._client_submissions:
                self._client_submissions[client_identifier] = []
            self._client_submissions[client_identifier].append(now)

    async def get_stats(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> dict:
        """Get statistics for monitoring."""

        if self.use_db:
            return await self._get_stats_db(session_identifier, client_identifier)
        else:
            return self._get_stats_memory(session_identifier, client_identifier)

    async def _get_stats_db(self, session_identifier: str, client_identifier: Optional[str]) -> dict:
        """Get stats from database."""

        try:
            async with self.db_pool.acquire() as conn:
                one_hour_ago = datetime.now() - timedelta(hours=1)
                one_day_ago = datetime.now() - timedelta(days=1)

                session_24h = await conn.fetchval("""
                    SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND created_at > $2
                """, session_identifier, one_day_ago)

                session_1h = await conn.fetchval("""
                    SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                    WHERE session_id = $1 AND created_at > $2
                """, session_identifier, one_hour_ago)

                is_blocked = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM mcp_performance.feedback_blocked_sessions
                        WHERE identifier = $1 AND identifier_type = 'session' AND unblock_at > NOW()
                    )
                """, session_identifier)

                stats = {
                    "session": {
                        "submissions_today": session_24h,
                        "submissions_this_hour": session_1h,
                        "remaining_today": max(0, self.session_max_per_day - session_24h),
                        "remaining_this_hour": max(0, self.session_max_per_hour - session_1h),
                        "is_blocked": is_blocked
                    }
                }

                if client_identifier:
                    client_24h = await conn.fetchval("""
                        SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                        WHERE client_id = $1 AND created_at > $2
                    """, client_identifier, one_day_ago)

                    client_1h = await conn.fetchval("""
                        SELECT COUNT(*) FROM mcp_performance.feedback_submissions
                        WHERE client_id = $1 AND created_at > $2
                    """, client_identifier, one_hour_ago)

                    client_blocked = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM mcp_performance.feedback_blocked_sessions
                            WHERE identifier = $1 AND identifier_type = 'client' AND unblock_at > NOW()
                        )
                    """, client_identifier)

                    stats["client"] = {
                        "submissions_today": client_24h,
                        "submissions_this_hour": client_1h,
                        "remaining_today": max(0, self.client_max_per_day - client_24h) if self.client_max_per_day else "unlimited",
                        "remaining_this_hour": max(0, self.client_max_per_hour - client_1h) if self.client_max_per_hour else "unlimited",
                        "is_blocked": client_blocked
                    }

                return stats

        except Exception as e:
            logger.error(f"Database error getting stats: {e}")
            return self._get_stats_memory(session_identifier, client_identifier)

    def _get_stats_memory(self, session_identifier: str, client_identifier: Optional[str]) -> dict:
        """Get stats from memory."""

        now = datetime.now()
        session_subs = self._session_submissions.get(session_identifier, [])
        session_24h = len([ts for ts in session_subs if now - ts < timedelta(days=1)])
        session_1h = len([ts for ts in session_subs if now - ts < timedelta(hours=1)])

        return {
            "session": {
                "submissions_today": session_24h,
                "submissions_this_hour": session_1h,
                "remaining_today": max(0, self.session_max_per_day - session_24h),
                "remaining_this_hour": max(0, self.session_max_per_hour - session_1h),
                "is_blocked": session_identifier in self._blocked_sessions
            }
        }


# Global instance (will be initialized with DB connection from server startup)
_safety_manager = None


def initialize_safety_manager(db_pool=None):
    """Initialize the global safety manager with optional DB connection."""
    global _safety_manager
    _safety_manager = FeedbackSafetyManagerDB(db_pool)
    return _safety_manager


def get_safety_manager() -> FeedbackSafetyManagerDB:
    """Get the global safety manager instance."""
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = FeedbackSafetyManagerDB()
    return _safety_manager
