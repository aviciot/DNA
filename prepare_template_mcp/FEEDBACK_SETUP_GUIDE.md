# Feedback System Setup Guide

## Overview

The template MCP includes an **optional** interactive feedback system that allows users to report bugs, request features, and suggest improvements directly through the MCP interface. The system automatically creates GitHub issues with quality checking and rate limiting.

**Status:** ⚠️ Disabled by default - requires configuration to enable

---

## Features

### Interactive Quality Checking
- Analyzes feedback quality (0-10 score)
- Identifies vague language, missing details, grammar issues
- Suggests improvements before submission
- LLM-powered rewriting for unclear feedback

### Multi-Level Rate Limiting
- **Per-user limits:** 3 submissions/hour, 10 submissions/day
- **Per-team limits:** 20 submissions/hour, 50 submissions/day
- Prevents spam and abuse
- Automatic duplicate detection

### GitHub Integration
- Creates GitHub issues automatically
- Adds appropriate labels (bug, feature, improvement)
- Includes quality scores and metadata
- Tracks submission status

### Admin Tools
- View feedback dashboard
- See GitHub issues summary
- Monitor rate limits and blocks
- Requires admin API key

---

## Quick Start

### Step 1: Enable Feedback System

Edit `server/config/settings.yaml`:

```yaml
feedback:
  enabled: true  # Change from false to true

  github:
    repo: "YOUR_USERNAME/YOUR_REPO"  # e.g., "aviciot/my-mcp-server"
    token_env: "GITHUB_TOKEN"
    maintainer: "YOUR_GITHUB_USERNAME"

  # Rate limits (optional - use defaults or customize)
  rate_limits:
    session:
      max_per_hour: 3
      max_per_day: 10
    client:
      max_per_hour: 20
      max_per_day: 50

  # Quality thresholds (optional)
  quality:
    auto_improve_threshold: 4.0
```

### Step 2: Set GitHub Token

Create a `.env` file in your project root:

```bash
GITHUB_TOKEN=github_pat_YOUR_TOKEN_HERE
```

**How to get a GitHub token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Personal access token (classic)"
3. Give it a name: "MCP Feedback System"
4. Select scopes: `repo` (full repository access)
5. Click "Generate token"
6. Copy the token and add it to `.env`

### Step 3: Configure Admin Access (Optional)

To use admin tools, add an "admin" API key:

```yaml
security:
  authentication:
    enabled: true

# Add admin key to your authentication system
```

### Step 4: Restart Server

```bash
# If using Docker
docker-compose restart

# If running locally
python server/server.py
```

---

## Available Tools

### User Tools (All Users)

#### `report_mcp_issue_interactive`
Report a bug, feature request, or improvement.

**Example:**
```python
{
  "issue_type": "bug",
  "title": "Query fails on large tables",
  "description": "When querying tables with >1M rows, the connection times out after 30 seconds. Expected: Should complete or show progress.",
  "auto_submit": false  # Preview first, then submit
}
```

**Flow:**
1. Quality check (score, suggestions)
2. Preview with labels
3. Submit to GitHub (if auto_submit=true)

#### `improve_my_feedback`
Get help improving unclear feedback.

**Example:**
```python
{
  "issue_type": "feature",
  "title": "add thing",
  "description": "need something for data"
}
```

Returns improved version with explanations.

#### `search_mcp_issues`
Search existing GitHub issues before creating new ones.

**Example:**
```python
{
  "query": "timeout",
  "issue_type": "bug",  # Optional filter
  "state": "open"  # open, closed, or all
}
```

### Admin Tools (Requires Admin API Key)

#### `get_feedback_dashboard`
View complete feedback dashboard.

```python
{
  "limit": 20,
  "status_filter": null,  # submitted, created, failed
  "type_filter": null  # bug, feature, improvement
}
```

#### `get_github_issues_summary`
See GitHub issues created from feedback.

```python
{
  "include_failed": false,
  "limit": 10
}
```

#### `get_feedback_by_client`
View specific team's feedback.

```python
{
  "client_id": "team-name",
  "limit": 20
}
```

---

## Configuration Reference

### Full Configuration Options

```yaml
feedback:
  enabled: false  # Set to true to enable

  # GitHub Integration (required if enabled)
  github:
    repo: "OWNER/REPO"
    token_env: "GITHUB_TOKEN"  # Environment variable name
    maintainer: "MAINTAINER_NAME"

  # Rate Limiting
  rate_limits:
    # Per-session (individual user)
    session:
      max_per_hour: 3
      max_per_day: 10

    # Per-client/team (optional)
    client:
      max_per_hour: 20
      max_per_day: 50

  # Quality Checking
  quality:
    min_title_length: 5
    max_title_length: 200
    min_description_length: 10
    max_description_length: 5000
    auto_improve_threshold: 4.0  # Suggest improvements below this score

  # Admin Access
  admin:
    api_key_name: "admin"  # Which API key has admin access
```

---

## Rate Limiting Explained

### Why Rate Limiting?

Prevents:
- Spam submissions
- Accidental duplicate submissions
- GitHub API quota exhaustion
- Low-quality feedback flooding

### Two-Level System

1. **Session-level** (per individual user)
   - Fair limits per person
   - Prevents single user from spamming

2. **Client-level** (per team/organization)
   - Prevents entire team from overwhelming maintainer
   - Shared quota across team members

### Automatic Unblocking

- Hourly limits reset after 60 minutes
- Daily limits reset after 24 hours
- No manual intervention needed

---

## Quality Checking Details

### Quality Score (0-10)

**Scoring factors:**
- **+2 points:** Good structure (sections, lists)
- **+2 points:** Specific examples
- **+2 points:** Clear steps to reproduce
- **-1 point:** Grammar issues
- **-2 points:** Vague language (something, maybe, somehow)
- **-3 points:** Missing required details

### Issue Type Requirements

**Bug reports should include:**
- What happened (actual behavior)
- What should happen (expected behavior)
- Steps to reproduce (if applicable)

**Feature requests should include:**
- What feature you want
- Why it's needed (use case)
- How it should work

**Improvements should include:**
- What to improve
- Why current state is problematic
- What would be better

### Interactive Improvement

If quality score < 4.0:
1. System shows issues found
2. Suggests improvements
3. User can use `improve_my_feedback` tool
4. LLM rewrites feedback to be clearer
5. User reviews and submits improved version

---

## Testing the System

### Test 1: Submit Feedback (Without Creating Issue)

```python
# Step 1: Report with auto_submit=false (preview only)
{
  "issue_type": "feature",
  "title": "Add caching support",
  "description": "Would be great to cache query results for better performance. Could save results in Redis or memory, with configurable TTL.",
  "auto_submit": false
}

# Expected: Quality check + preview, no GitHub issue created
```

### Test 2: Quality Improvement

```python
# Step 1: Submit poor quality feedback
{
  "issue_type": "bug",
  "title": "thing broken",
  "description": "something doesnt work maybe",
  "auto_submit": false
}

# Expected: Low quality score, improvement suggestions

# Step 2: Use improvement tool
{
  "issue_type": "bug",
  "title": "thing broken",
  "description": "something doesnt work maybe"
}

# Expected: Improved version with clear title and description
```

### Test 3: Rate Limiting

```python
# Submit 4 issues rapidly
# Expected: 4th submission blocked with rate limit message
```

### Test 4: Admin Tools

```python
# With admin API key:
{
  "limit": 10
}

# Expected: Dashboard with statistics

# Without admin API key:
# Expected: "🔒 Access denied. Admin access required."
```

---

## Architecture

### Components

```
feedback_context.py       # Session tracking (contextvars)
feedback_safety.py        # Rate limiting & validation
feedback_quality.py       # Quality analysis & scoring
mcp_feedback.py          # Main feedback tools
feedback_admin.py        # Admin-only tools
feedback_improvement.py  # LLM improvement prompt
mcp_welcome.py          # Welcome resource
```

### Request Flow

```
1. User calls report_mcp_issue_interactive
   ↓
2. SessionContextMiddleware sets context
   ↓
3. Rate limit check (session + client)
   ↓
4. Content validation (length, spam patterns)
   ↓
5. Duplicate detection
   ↓
6. Quality analysis (0-10 score)
   ↓
7. If low quality: suggest improvement
   ↓
8. Generate preview
   ↓
9. If auto_submit=true: create GitHub issue
   ↓
10. Record submission for rate limiting
```

### Session Tracking

- Uses Python `contextvars` for request-scoped data
- Session ID from request headers or generated
- Client ID from API key
- Composite identifier: `{client_id}:{session_id}`

---

## Customization

### Change Rate Limits

Edit `settings.yaml`:

```yaml
rate_limits:
  session:
    max_per_hour: 5  # Increase from 3
    max_per_day: 20  # Increase from 10
  client:
    max_per_hour: 50  # Increase from 20
    max_per_day: 100  # Increase from 50
```

### Disable Team-Level Limits

```yaml
rate_limits:
  session:
    max_per_hour: 3
    max_per_day: 10
  client:
    max_per_hour: null  # Disable team limits
    max_per_day: null
```

### Adjust Quality Thresholds

```yaml
quality:
  auto_improve_threshold: 6.0  # Stricter (suggest improvements for scores < 6)
  min_description_length: 50  # Require longer descriptions
```

### Custom Labels

Edit `mcp_feedback.py`:

```python
labels = [issue_type, "user-submitted", "automated", "needs-triage"]
```

---

## Troubleshooting

### Issue: Feedback system not loading

**Symptoms:** Tools not appearing

**Fix:**
1. Check `feedback.enabled: true` in settings.yaml
2. Verify all feedback files are in `server/tools/`
3. Restart server
4. Check logs for import errors

### Issue: GitHub API errors

**Symptoms:** "Failed to create GitHub issue"

**Fix:**
1. Verify GITHUB_TOKEN is set in `.env`
2. Check token has `repo` scope
3. Verify repo name format: "owner/repo"
4. Check GitHub API rate limits

### Issue: Admin tools not working

**Symptoms:** "Access denied"

**Fix:**
1. Ensure API key name is exactly "admin"
2. Check authentication is enabled
3. Verify using correct API key header

### Issue: Rate limits too strict

**Symptoms:** Users blocked frequently

**Fix:**
1. Increase limits in settings.yaml
2. Or disable client-level limits (set to null)
3. Restart server for changes to take effect

---

## Security Considerations

### Rate Limiting

- Prevents abuse and spam
- Protects GitHub API quota
- Maintains maintainer sanity

### Admin Access

- Only "admin" API key can view feedback dashboard
- Sensitive information (sessions, blocks) protected
- Audit logging for admin actions

### Content Validation

- Checks for spam patterns
- Blocks excessive caps, repeated characters
- Validates URLs (only github.com allowed)
- Limits description length

### Session Tracking

- No PII collected
- Session IDs are ephemeral
- Client IDs hashed from API keys

---

## Best Practices

### For Users

1. **Search first** - Use `search_mcp_issues` before creating new issues
2. **Be specific** - Include examples, steps, error messages
3. **One issue per submission** - Don't combine multiple bugs/features
4. **Preview before submitting** - Use `auto_submit=false` first
5. **Check quality score** - Aim for 7+ for best results

### For Maintainers

1. **Monitor admin dashboard** - Check for patterns, spam
2. **Adjust rate limits** - Based on community size and activity
3. **Label consistently** - Add custom labels for your workflow
4. **Respond promptly** - Acknowledge feedback on GitHub
5. **Close duplicates** - Merge similar issues

### For Template Users

1. **Customize welcome message** - Edit `mcp_welcome.py`
2. **Adjust quality thresholds** - Match your community's needs
3. **Set up GitHub notifications** - Get alerts for new issues
4. **Document feedback process** - Tell users how to report issues
5. **Review and iterate** - Improve based on feedback patterns

---

## Disabling the Feedback System

If you don't want the feedback system:

### Option 1: Disable in Config (Recommended)

```yaml
feedback:
  enabled: false
```

Tools will still be present but will return "Feedback system is not enabled".

### Option 2: Remove Files (Complete Removal)

Delete these files:
```
server/tools/feedback_*.py
server/tools/mcp_feedback.py
server/prompts/feedback_improvement.py
server/resources/mcp_welcome.py
```

Remove from `settings.yaml`:
```yaml
# Delete entire feedback section
```

---

## Support

**Issues with feedback system?**

1. Check this guide first
2. Review server logs for errors
3. Test with example payloads above
4. Check GitHub token permissions

**Found a bug in the feedback system itself?**

Use the feedback system to report it! 😄

---

**Status:** ✅ Ready to use (after configuration)

**Version:** 1.0.0

**Last Updated:** 2026-01-19
