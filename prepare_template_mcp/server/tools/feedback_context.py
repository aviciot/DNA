"""
Context management for feedback system - tracks current request/session.

GENERIC MODULE: Copy to any MCP for session tracking.
No modifications needed when reusing.
"""

from contextvars import ContextVar
from typing import Optional

# Context variables for request-scoped data
_current_session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
_current_user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
_current_client_id: ContextVar[Optional[str]] = ContextVar('client_id', default=None)


def set_request_context(session_id: str, user_id: str, client_id: str = None):
    """
    Set request context (called by middleware).

    Args:
        session_id: Unique session identifier from MCP transport
        user_id: User/team identifier from API key (may be shared)
        client_id: Client identifier (same as user_id but clearer naming)
    """
    _current_session_id.set(session_id)
    _current_user_id.set(user_id)
    _current_client_id.set(client_id or user_id)


def get_session_id() -> str:
    """Get current session ID."""
    session_id = _current_session_id.get()
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        _current_session_id.set(session_id)
    return session_id


def get_client_id() -> str:
    """Get current client/team ID from API key."""
    client_id = _current_client_id.get()
    if not client_id:
        client_id = "anonymous"
    return client_id


def get_user_identifier() -> str:
    """
    Get composite identifier for rate limiting.

    Format: "{client_id}:{session_id}"

    This ensures:
    - Different users with same API key get separate limits
    - Same user across sessions maintains continuity
    - Can track team/client-level usage
    """
    client_id = get_client_id()
    session_id = get_session_id()

    # Composite identifier
    return f"{client_id}:{session_id}"


def get_client_identifier() -> str:
    """
    Get client-only identifier (for team-level tracking).

    Use this for:
    - Team-level rate limits (optional)
    - Analytics/reporting
    - Billing/usage tracking
    """
    return get_client_id()


def get_tracking_info() -> dict:
    """
    Get complete tracking information.

    Returns:
        dict with session_id, client_id, and composite identifier
    """
    return {
        "session_id": get_session_id(),
        "client_id": get_client_id(),
        "user_identifier": get_user_identifier(),
        "client_identifier": get_client_identifier()
    }
