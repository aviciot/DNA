"""
Safety layer for MCP feedback system - prevents abuse.

GENERIC MODULE: Copy to any MCP for rate limiting and validation.
Reads configuration from settings.yaml - no code changes needed.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FeedbackSafetyManager:
    """
    Multi-level rate limiting and content validation:
    1. Per-session limits (individual user)
    2. Per-client limits (team/organization)
    3. Content validation (spam, quality)
    4. Duplicate detection
    """

    def __init__(self):
        # Per-session tracking (fine-grained)
        self._session_submissions: Dict[str, List[datetime]] = {}
        self._session_hashes: Dict[str, datetime] = {}
        self._blocked_sessions: Dict[str, datetime] = {}

        # Per-client tracking (team-level)
        self._client_submissions: Dict[str, List[datetime]] = {}
        self._blocked_clients: Dict[str, datetime] = {}

        # Configuration - Per Session (Individual User)
        self.session_max_per_hour = 3
        self.session_max_per_day = 10

        # Configuration - Per Client/Team (set to None to disable)
        self.client_max_per_hour = 20  # Team can submit 20/hour total
        self.client_max_per_day = 50   # Team can submit 50/day total

        # Other config
        self.duplicate_window_minutes = 30
        self.block_duration_hours = 24
        self.max_description_length = 5000
        self.max_title_length = 200

    def check_rate_limit(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check rate limits at both session and client level.

        Args:
            session_identifier: Composite "{client}:{session}"
            client_identifier: Client ID only (for team-level check)
        """

        now = datetime.now()

        # Extract client_id from composite identifier
        parts = session_identifier.split(":", 1)
        client_id = parts[0] if len(parts) > 1 else "unknown"

        # LEVEL 1: Check session-level block
        if session_identifier in self._blocked_sessions:
            unblock_at = self._blocked_sessions[session_identifier]
            if now < unblock_at:
                hours_left = int((unblock_at - now).total_seconds() / 3600)
                return False, (
                    f"⛔ **You are temporarily blocked**\n\n"
                    f"Reason: Rate limit exceeded\n"
                    f"Time remaining: ~{hours_left} hours\n\n"
                    f"This helps maintain quality and prevent spam."
                )
            else:
                del self._blocked_sessions[session_identifier]
                logger.info(f"✅ Session {session_identifier[:20]} automatically unblocked")

        # LEVEL 2: Check client-level block (team-wide)
        if client_identifier and client_identifier in self._blocked_clients:
            unblock_at = self._blocked_clients[client_identifier]
            if now < unblock_at:
                hours_left = int((unblock_at - now).total_seconds() / 3600)
                return False, (
                    f"⛔ **Your team/organization is temporarily blocked**\n\n"
                    f"Reason: Team rate limit exceeded\n"
                    f"Time remaining: ~{hours_left} hours\n\n"
                    f"Please coordinate with your team to manage feedback submissions."
                )
            else:
                del self._blocked_clients[client_identifier]
                logger.info(f"✅ Client {client_identifier} automatically unblocked")

        # Clean old submissions
        if session_identifier not in self._session_submissions:
            self._session_submissions[session_identifier] = []

        self._session_submissions[session_identifier] = [
            ts for ts in self._session_submissions[session_identifier]
            if now - ts < timedelta(days=1)
        ]

        session_subs = self._session_submissions[session_identifier]

        # LEVEL 3: Check session hourly limit
        session_last_hour = [ts for ts in session_subs if now - ts < timedelta(hours=1)]
        if len(session_last_hour) >= self.session_max_per_hour:
            minutes_wait = 60 - int((now - session_last_hour[0]).total_seconds() / 60)
            return False, (
                f"⏱️ **Hourly Rate Limit Reached**\n\n"
                f"Your limit: {self.session_max_per_hour} submissions per hour\n"
                f"Wait time: {minutes_wait} minutes\n\n"
                f"💡 **Tip:** Search existing issues first!\n"
                f"Say: 'Search issues about [topic]'"
            )

        # LEVEL 4: Check session daily limit
        if len(session_subs) >= self.session_max_per_day:
            return False, (
                f"📊 **Daily Limit Reached**\n\n"
                f"Your limit: {self.session_max_per_day} submissions per day\n"
                f"Current: {len(session_subs)} submissions today\n\n"
                f"You can submit more feedback tomorrow!"
            )

        # LEVEL 5: Check client/team limits (if enabled)
        if client_identifier and self.client_max_per_hour:
            if client_identifier not in self._client_submissions:
                self._client_submissions[client_identifier] = []

            self._client_submissions[client_identifier] = [
                ts for ts in self._client_submissions[client_identifier]
                if now - ts < timedelta(days=1)
            ]

            client_subs = self._client_submissions[client_identifier]

            # Check team hourly limit
            client_last_hour = [ts for ts in client_subs if now - ts < timedelta(hours=1)]
            if len(client_last_hour) >= self.client_max_per_hour:
                minutes_wait = 60 - int((now - client_last_hour[0]).total_seconds() / 60)
                return False, (
                    f"🏢 **Team Hourly Limit Reached**\n\n"
                    f"Team limit: {self.client_max_per_hour} submissions per hour\n"
                    f"Current: {len(client_last_hour)} by your team this hour\n"
                    f"Wait time: {minutes_wait} minutes\n\n"
                    f"💡 **Tip:** Coordinate with your team to avoid hitting team limits."
                )

            # Check team daily limit
            if self.client_max_per_day and len(client_subs) >= self.client_max_per_day:
                return False, (
                    f"🏢 **Team Daily Limit Reached**\n\n"
                    f"Team limit: {self.client_max_per_day} submissions per day\n"
                    f"Current: {len(client_subs)} submissions by your team today\n\n"
                    f"Your team can submit more feedback tomorrow."
                )

        return True, ""

    def check_duplicate(self, session_identifier: str, content: str) -> Tuple[bool, str]:
        """Check for duplicate submissions by this specific user/session."""

        content_hash = hashlib.md5(content.lower().encode()).hexdigest()
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
                    f"Wait time: {minutes_left} minutes\n\n"
                    f"💡 Did you mean to add more information?\n"
                    f"You can search for your issue and add a comment instead."
                )

        return False, ""

    def validate_content(self, title: str, description: str) -> Tuple[bool, str]:
        """Validate content for safety and quality."""

        # Check lengths
        if len(title) > self.max_title_length:
            return False, (
                f"❌ **Title Too Long**\n\n"
                f"Maximum: {self.max_title_length} characters\n"
                f"Current: {len(title)} characters\n\n"
                f"Please shorten your title to be more concise."
            )

        if len(title) < 5:
            return False, (
                "❌ **Title Too Short**\n\n"
                "Minimum: 5 characters\n\n"
                "Please provide a descriptive title."
            )

        if len(description) > self.max_description_length:
            return False, (
                f"❌ **Description Too Long**\n\n"
                f"Maximum: {self.max_description_length} characters\n"
                f"Current: {len(description)} characters\n\n"
                f"Please be more concise or split into multiple issues."
            )

        if len(description) < 10:
            return False, (
                "❌ **Description Too Short**\n\n"
                "Minimum: 10 characters\n\n"
                "Please provide more details to help us understand the issue."
            )

        # Check for spam patterns
        spam_patterns = [
            (r'(.)\1{20,}', "repeated characters"),
            (r'http[s]?://(?!github\.com)', "external links (only github.com allowed)"),
            (r'\b(buy|sell|click here|subscribe|download now)\b', "promotional content"),
            (r'[A-Z]{50,}', "excessive caps (looks like shouting)"),
        ]

        combined = f"{title} {description}".lower()

        for pattern, reason in spam_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return False, (
                    f"⚠️ **Potential Spam Detected**\n\n"
                    f"Issue: {reason}\n\n"
                    f"If this is legitimate feedback, please rephrase and try again."
                )

        return True, ""

    def record_submission(
        self,
        session_identifier: str,
        client_identifier: Optional[str],
        content: str
    ):
        """Record submission at both session and client level."""

        now = datetime.now()

        # Record session-level
        if session_identifier not in self._session_submissions:
            self._session_submissions[session_identifier] = []
        self._session_submissions[session_identifier].append(now)

        # Record duplicate hash
        content_hash = hashlib.md5(content.lower().encode()).hexdigest()
        key = f"{session_identifier}:{content_hash}"
        self._session_hashes[key] = now

        # Record client-level
        if client_identifier:
            if client_identifier not in self._client_submissions:
                self._client_submissions[client_identifier] = []
            self._client_submissions[client_identifier].append(now)

        # Check for abuse and auto-block
        session_recent = [
            ts for ts in self._session_submissions[session_identifier]
            if now - ts < timedelta(hours=1)
        ]

        if len(session_recent) >= self.session_max_per_hour * 2:
            self._blocked_sessions[session_identifier] = now + timedelta(hours=self.block_duration_hours)
            logger.warning(f"🚫 Auto-blocked session: {session_identifier[:30]}")

    def get_stats(
        self,
        session_identifier: str,
        client_identifier: Optional[str] = None
    ) -> dict:
        """Get statistics for session and optionally client."""

        now = datetime.now()

        # Session stats
        session_subs = self._session_submissions.get(session_identifier, [])
        session_24h = len([ts for ts in session_subs if now - ts < timedelta(days=1)])
        session_1h = len([ts for ts in session_subs if now - ts < timedelta(hours=1)])

        stats = {
            "session": {
                "submissions_today": session_24h,
                "submissions_this_hour": session_1h,
                "remaining_today": max(0, self.session_max_per_day - session_24h),
                "remaining_this_hour": max(0, self.session_max_per_hour - session_1h),
                "is_blocked": session_identifier in self._blocked_sessions
            }
        }

        # Client/team stats
        if client_identifier:
            client_subs = self._client_submissions.get(client_identifier, [])
            client_24h = len([ts for ts in client_subs if now - ts < timedelta(days=1)])
            client_1h = len([ts for ts in client_subs if now - ts < timedelta(hours=1)])

            stats["client"] = {
                "submissions_today": client_24h,
                "submissions_this_hour": client_1h,
                "remaining_today": max(0, self.client_max_per_day - client_24h) if self.client_max_per_day else "unlimited",
                "remaining_this_hour": max(0, self.client_max_per_hour - client_1h) if self.client_max_per_hour else "unlimited",
                "is_blocked": client_identifier in self._blocked_clients
            }

        return stats


# Global instance
_safety_manager = FeedbackSafetyManager()


def get_safety_manager() -> FeedbackSafetyManager:
    """Get the global safety manager instance."""
    return _safety_manager
