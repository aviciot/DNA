"""
Welcome resource for Performance MCP - Introduces feedback system
Explains how users can report bugs, suggest features, and contribute
"""

from mcp_app import mcp
import os


def is_feedback_enabled():
    """Check if feedback system is configured."""
    try:
        import yaml
        with open("/app/config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)
            return config.get("feedback", {}).get("enabled", False)
    except:
        return False


@mcp.resource("welcome://feedback-system")
def get_feedback_welcome() -> str:
    """
    Introduction to the MCP feedback system - How to report issues and suggest improvements
    """

    if not is_feedback_enabled():
        return """# Help Improve This MCP

The interactive feedback system is currently being configured.
Check back soon for the ability to report bugs and suggest improvements!
"""

    return """# 🎉 Welcome to Performance MCP

## 💬 Help Us Improve!

This MCP includes an **interactive feedback system** to help you report bugs, request features, and suggest improvements.

### 📝 How to Provide Feedback

**Three ways to contribute:**

1. **🐛 Report a Bug**
   ```
   Use tool: report_mcp_issue_interactive
   Type: "bug"
   Example: "Query analysis fails for MERGE statements"
   ```

2. **✨ Request a Feature**
   ```
   Use tool: report_mcp_issue_interactive
   Type: "feature"
   Example: "Add support for PostgreSQL databases"
   ```

3. **🔧 Suggest an Improvement**
   ```
   Use tool: report_mcp_issue_interactive
   Type: "improvement"
   Example: "Make error messages more user-friendly"
   ```

### 🌟 What Makes This Special

**Interactive Quality Checking:**
- Your feedback is analyzed for clarity
- I'll help improve unclear descriptions (even broken English!)
- You preview before submitting to GitHub
- No gatekeeping - suggestions only

**Smart Rate Limiting:**
- 3 submissions per hour
- 10 submissions per day
- Fair limits prevent spam while encouraging feedback

**Search Before Submit:**
- Use `search_mcp_issues` to avoid duplicates
- Find existing issues and add your input
- See if there's already a workaround

### 📋 Examples of Good Feedback

**Bug Report Example:**
```
Title: "analyze_oracle_query returns empty plan_details for MERGE"
Description:
When analyzing a MERGE INTO statement, plan_details is empty.

Steps to reproduce:
1. Call analyze_oracle_query with MERGE statement
2. Check plan_details in response
3. It's an empty array

Expected: Should return execution plan
Actual: Empty array
Environment: Oracle 19c
```

**Feature Request Example:**
```
Title: "Add PostgreSQL database support"
Description:
Add PostgreSQL query analysis alongside Oracle/MySQL.

Use case: Many teams use PostgreSQL and would benefit from
the same performance analysis capabilities.

Expected behavior:
- Connect to PostgreSQL databases
- Analyze queries with EXPLAIN
- Get index recommendations

Benefits: Broader database support for more teams
```

**Improvement Example:**
```
Title: "Add query execution time estimates"
Description:
Currently we see execution plans but no time estimates.

Current limitation: Hard to prioritize optimizations without
knowing which queries are actually slowest.

Proposed: Add estimated execution time based on plan cost
and historical statistics.

Expected outcome: Better prioritization of optimization efforts
```

### 🚀 Interactive Workflow

1. **Call the tool:**
   ```
   report_mcp_issue_interactive(
     issue_type="bug",
     title="Your clear title",
     description="Detailed description"
   )
   ```

2. **Quality check:**
   - Instant analysis of your feedback
   - Suggestions for improvement
   - Score out of 10

3. **Improve if needed:**
   ```
   improve_my_feedback(
     issue_type="bug",
     title="original title",
     description="original description"
   )
   ```
   I'll help rewrite it to be clearer!

4. **Preview and confirm:**
   - See exactly what will be posted
   - Check labels and formatting
   - Submit with `auto_submit=True`

5. **Track on GitHub:**
   - Get direct link to your issue
   - Follow progress and discussion
   - Contribute additional context

### 🔍 Search First!

Before creating a new issue:
```
search_mcp_issues(
  query="your search terms",
  issue_type="bug",  # optional
  state="open"       # or "closed" or "all"
)
```

Benefits:
- Find existing reports of your issue
- Add details to existing issues
- See if there's a workaround
- Avoid duplicate submissions

### ✨ Quality Tips

**DO:**
- Be specific (exact error messages, steps, examples)
- Include context (when, where, what you expected)
- Structure with bullet points or numbers
- Mention your environment (Oracle 19c, MySQL 8.0, etc.)

**DON'T:**
- Use vague words like "something", "somehow", "maybe"
- Skip details about what you expected vs what happened
- Worry about perfect English (I'll help improve it!)
- Submit duplicates (search first!)

### 🛡️ Safety & Privacy

**Content Validation:**
- Automatic spam detection
- Duplicate prevention (30-minute window)
- Length limits (5-200 chars title, 10-5000 chars description)
- Sensitive data sanitization

**Rate Limits:**
- Per-user: 3/hour, 10/day
- Per-team: 20/hour, 50/day (if token is shared)
- Auto-unblock after 24 hours
- Fair usage for everyone

**What's Tracked:**
- Session ID (to prevent spam)
- Client ID (for team limits)
- Submission timestamps
- Nothing personally identifiable

### 🤝 Why Your Feedback Matters

Every bug report, feature request, and improvement suggestion helps:
- Fix issues other users face
- Guide feature prioritization
- Improve documentation
- Build a better tool for everyone

**Your feedback shapes the future of this MCP!**

### 📚 Quick Command Reference

```python
# Report an issue
report_mcp_issue_interactive(
    issue_type="bug",
    title="Clear title here",
    description="Detailed description here",
    auto_submit=False  # Preview first
)

# Search existing issues
search_mcp_issues(
    query="keywords to search",
    issue_type="bug",  # optional
    state="open"
)

# Get help improving feedback
improve_my_feedback(
    issue_type="bug",
    title="your title",
    description="your description"
)
```

---

**Ready to help improve this MCP?**

Just tell me about any bugs, features, or improvements you'd like to see!
I'll guide you through the interactive feedback process.

🎯 Remember: There are no bad suggestions, only opportunities to make this better together!
"""


@mcp.resource("welcome://feedback-examples")
def get_feedback_examples() -> dict:
    """
    Concrete examples of feedback submissions in different scenarios
    """

    return {
        "purpose": "Real-world examples of how to use the feedback system",

        "scenario_1_bug_report": {
            "situation": "User encounters error when analyzing a specific query type",
            "conversation": [
                {
                    "user": "I tried to analyze a MERGE statement but got an empty plan_details array. SELECT queries work fine though.",
                    "assistant": "That sounds like a bug. Let me help you report it. I'll create a clear bug report.",
                    "tool_call": {
                        "tool": "report_mcp_issue_interactive",
                        "args": {
                            "issue_type": "bug",
                            "title": "analyze_oracle_query returns empty plan_details for MERGE statements",
                            "description": "When analyzing a MERGE INTO statement using analyze_oracle_query, the returned plan_details array is empty.\n\nSteps to reproduce:\n1. Call analyze_oracle_query with a MERGE INTO statement\n2. Check plan_details in the response\n3. Observe that it's an empty array\n\nExpected: plan_details should contain execution plan steps\nActual: plan_details is []\n\nEnvironment: Oracle 19c\nNote: SELECT queries work correctly",
                            "auto_submit": False
                        }
                    },
                    "result": "Quality score 8.5/10 - Preview shown, user confirms, issue created"
                }
            ],
            "key_takeaways": [
                "Be specific about what works vs what doesn't",
                "Include steps to reproduce",
                "Mention your environment",
                "Compare expected vs actual behavior"
            ]
        },

        "scenario_2_feature_request": {
            "situation": "User wants support for a new database type",
            "conversation": [
                {
                    "user": "Would be nice if this worked with PostgreSQL too, not just Oracle and MySQL",
                    "assistant": "Good idea! Let me help you create a feature request.",
                    "tool_call": {
                        "tool": "report_mcp_issue_interactive",
                        "args": {
                            "issue_type": "feature",
                            "title": "add support for mysql",
                            "description": "would be nice if we could use this with mysql not just oracle",
                            "auto_submit": False
                        }
                    },
                    "result": "Quality score 4.2/10 - Tool suggests improvement"
                },
                {
                    "assistant": "Your feedback scored 4.2/10. Let me help improve it for clarity.",
                    "tool_call": {
                        "tool": "improve_my_feedback",
                        "args": {
                            "issue_type": "feature",
                            "title": "add support for mysql",
                            "description": "would be nice if we could use this with mysql not just oracle"
                        }
                    },
                    "result": {
                        "improved_title": "Add PostgreSQL database support alongside Oracle and MySQL",
                        "improved_description": "Add support for analyzing PostgreSQL queries in addition to current Oracle/MySQL support.\n\nUse case: Many teams use PostgreSQL databases and would benefit from the same query analysis capabilities.\n\nExpected behavior:\n- Connect to PostgreSQL databases\n- Analyze queries with EXPLAIN\n- Get index recommendations\n- Query optimization suggestions\n\nBenefits: Broader database support for more development teams",
                        "changes_made": [
                            "Made title more specific and professional",
                            "Added clear use case",
                            "Listed expected features",
                            "Explained benefits"
                        ]
                    }
                },
                {
                    "user": "Yes that's better, submit it",
                    "assistant": "Submitting improved version...",
                    "result": "Issue #42 created successfully"
                }
            ],
            "key_takeaways": [
                "Interactive improvement helps unclear feedback",
                "LLM preserves user's meaning while improving clarity",
                "User always has final approval",
                "Quality checking is helpful, not gatekeeping"
            ]
        },

        "scenario_3_improvement": {
            "situation": "User wants better error messages",
            "conversation": [
                {
                    "user": "When queries fail, the error messages are too technical. Can we make them more user-friendly?",
                    "assistant": "Absolutely! That's a great improvement suggestion. Let me create that for you.",
                    "tool_call": {
                        "tool": "report_mcp_issue_interactive",
                        "args": {
                            "issue_type": "improvement",
                            "title": "Make error messages more user-friendly",
                            "description": "Current error messages are too technical and hard to understand for non-DBAs.\n\nCurrent state: Errors show raw Oracle/MySQL error codes and technical messages.\n\nProblem: Users without deep database knowledge can't understand what went wrong or how to fix it.\n\nProposed improvement: Add plain-language explanations and actionable suggestions.\n\nExample:\nCurrent: 'ORA-00942: table or view does not exist'\nBetter: 'Table not found. Check: 1) Table name spelling, 2) Schema name, 3) Database permissions'\n\nExpected outcome: Users can self-solve common issues instead of needing expert help.",
                            "auto_submit": False
                        }
                    },
                    "result": "Quality score 8.8/10 - Clear and actionable, preview shown"
                },
                {
                    "user": "Looks good, submit it",
                    "result": "Issue #43 created successfully with labels: improvement, user-experience, good-quality"
                }
            ],
            "key_takeaways": [
                "Explain current state and why it's problematic",
                "Give concrete examples",
                "Describe expected outcome",
                "Show the value/benefit of the change"
            ]
        },

        "scenario_4_search_first": {
            "situation": "User wants to report something but checks for duplicates first",
            "conversation": [
                {
                    "user": "The query analysis seems slow for large tables. Has anyone reported this?",
                    "assistant": "Good question! Let me search existing issues first.",
                    "tool_call": {
                        "tool": "search_mcp_issues",
                        "args": {
                            "query": "slow performance large tables",
                            "state": "all"
                        }
                    },
                    "result": {
                        "count": 2,
                        "issues": [
                            {
                                "number": 15,
                                "title": "Performance degradation with tables >10M rows",
                                "state": "closed",
                                "url": "https://github.com/owner/repo/issues/15",
                                "labels": ["performance", "resolved"]
                            },
                            {
                                "number": 38,
                                "title": "Add caching for table statistics",
                                "state": "open",
                                "url": "https://github.com/owner/repo/issues/38",
                                "labels": ["enhancement", "performance"]
                            }
                        ]
                    }
                },
                {
                    "assistant": "Found 2 related issues! Issue #15 was resolved, and #38 is actively being worked on. You can add details to #38 if your case is similar.",
                    "user": "Thanks, I'll check #38 and add my observations there!",
                    "result": "Avoided duplicate, contributed to existing conversation"
                }
            ],
            "key_takeaways": [
                "Always search before creating new issues",
                "Closed issues might have solutions",
                "Open issues welcome additional context",
                "Collaboration improves quality"
            ]
        },

        "best_practices": [
            "Search existing issues first (avoid duplicates)",
            "Be specific with examples and steps",
            "Include your environment (Oracle version, etc.)",
            "Don't worry about perfect English (we'll help improve)",
            "Preview before submitting (catch mistakes)",
            "Quality tips are suggestions, not requirements",
            "One issue per submission (don't bundle multiple topics)"
        ],

        "common_mistakes": [
            "Vague descriptions: 'something doesn't work' → Be specific!",
            "No context: 'Query slow' → Which query? How slow? Expected?",
            "Bundling: 'Fix bugs X, Y, Z and add features A, B' → One issue each",
            "Skipping search: Duplicates waste everyone's time",
            "Auto-submitting low quality: Preview and improve first"
        ]
    }


@mcp.resource("welcome://feedback-faq")
def get_feedback_faq() -> dict:
    """
    Frequently asked questions about the feedback system
    """

    return {
        "title": "Feedback System - FAQ",

        "general": {
            "q1": {
                "question": "Why do I need to preview before submitting?",
                "answer": "Previewing lets you catch typos, verify clarity, and ensure your issue will be understood. It takes 5 seconds and prevents miscommunication."
            },
            "q2": {
                "question": "What if my English is not good?",
                "answer": "No problem! Use `improve_my_feedback` and I'll help rewrite it to be clearer while keeping your exact meaning. The system is designed to be inclusive."
            },
            "q3": {
                "question": "Can I submit feedback anonymously?",
                "answer": "Issues are posted to GitHub with a session ID (not your personal info). However, GitHub issues are public, so don't include sensitive data."
            }
        },

        "rate_limits": {
            "q1": {
                "question": "Why are there rate limits?",
                "answer": "Rate limits prevent spam and abuse while allowing plenty of legitimate feedback (3/hour, 10/day per user). They ensure the system stays available for everyone."
            },
            "q2": {
                "question": "What if I hit the rate limit?",
                "answer": "Wait a bit! Limits reset hourly and daily. If you have urgent feedback, you can also email the maintainer directly or contribute via GitHub PRs."
            },
            "q3": {
                "question": "Do team members share rate limits?",
                "answer": "Each person gets their own limits (3/hour, 10/day). Additionally, there's a team limit (20/hour, 50/day) to prevent one team from overwhelming the system."
            }
        },

        "quality_checking": {
            "q1": {
                "question": "What if my feedback scores low on quality?",
                "answer": "Low scores are just suggestions! You can: 1) Use improve_my_feedback to get help, 2) Edit and resubmit, or 3) Submit as-is with auto_submit=True. No gatekeeping."
            },
            "q2": {
                "question": "What makes feedback 'good quality'?",
                "answer": "Specific details, clear structure, examples, and context. Think: What happened? What should happen? Steps to reproduce? Examples? Environment?"
            },
            "q3": {
                "question": "Will low-quality feedback be rejected?",
                "answer": "No! Quality checking is guidance, not enforcement. We accept all legitimate feedback. Better clarity just helps maintainers understand and fix faster."
            }
        },

        "privacy_security": {
            "q1": {
                "question": "What data is tracked?",
                "answer": "Only session ID, client ID, and submission timestamps for rate limiting. No personal information. Issues are posted to public GitHub."
            },
            "q2": {
                "question": "Can I include sensitive information?",
                "answer": "NO! Don't include passwords, API keys, customer data, etc. Issues are PUBLIC on GitHub. Focus on the problem, not sensitive details."
            },
            "q3": {
                "question": "How long is my data stored?",
                "answer": "Rate limit tracking data (timestamps) is kept in memory for 24 hours, then automatically cleared. GitHub issues are permanent public records."
            }
        },

        "workflow": {
            "q1": {
                "question": "Do I need to create a GitHub account?",
                "answer": "No! The MCP creates issues on your behalf using the maintainer's GitHub token. Issues will be labeled 'user-submitted' to show they came via MCP."
            },
            "q2": {
                "question": "How do I track my submitted issues?",
                "answer": "After submission, you get a direct GitHub URL. Bookmark it or use search_mcp_issues later to find it. You can follow progress there."
            },
            "q3": {
                "question": "Can I update my issue after submitting?",
                "answer": "Yes! Visit the GitHub URL and add comments. Or create a new related issue referencing the old one. The maintainer will see all updates."
            }
        },

        "troubleshooting": {
            "q1": {
                "question": "My submission failed. What now?",
                "answer": "Check: 1) Is feedback system enabled? 2) Is GitHub token configured? 3) Did you hit rate limit? 4) Is content valid? The error message will guide you."
            },
            "q2": {
                "question": "I can't find my submitted issue on GitHub",
                "answer": "Use search_mcp_issues with keywords from your title. GitHub search may take a few minutes to index new issues. Check the direct URL from submission response."
            },
            "q3": {
                "question": "Quality checker says I need improvements but I disagree",
                "answer": "Submit anyway with auto_submit=True! Quality checking is advisory. If you think your feedback is clear, go ahead. The maintainer decides what's valid."
            }
        },

        "advanced": {
            "q1": {
                "question": "Can I submit feedback programmatically?",
                "answer": "Yes! Call report_mcp_issue_interactive() with auto_submit=True to skip interactive steps. Useful for automated error reporting or batch submissions."
            },
            "q2": {
                "question": "How can I contribute code changes instead of issues?",
                "answer": "Great! Fork the repo on GitHub, make your changes, and open a Pull Request. Code contributions are always welcome alongside issue reports."
            },
            "q3": {
                "question": "Can this feedback system be added to my MCP?",
                "answer": "Absolutely! Copy feedback_context.py, feedback_safety.py, feedback_quality.py, mcp_feedback.py, update settings.yaml, and you're set. It's designed to be generic."
            }
        }
    }
