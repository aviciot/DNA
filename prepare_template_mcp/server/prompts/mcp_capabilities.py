"""MCP capabilities description - helps LLM understand scope."""

from mcp_app import mcp


@mcp.prompt(
    name="mcp_capabilities",
    description="Describes what this MCP does - use before reporting issues"
)
async def get_mcp_capabilities():
    """
    Returns a clear description of MCP capabilities.
    LLM should read this to understand scope before validating feedback.
    """
    return """
# Template MCP - Capabilities

## What This MCP Does

This is a template/starter MCP that demonstrates best practices for building MCP servers.

### Core Features
1. **MCP Server Infrastructure**
   - FastMCP framework integration
   - Authentication middleware
   - Auto-discovery of tools/resources/prompts
   - Configuration management

2. **Example Tools**
   - Sample tool implementations
   - Best practice patterns
   - Error handling examples

3. **Feedback System**
   - GitHub issue integration
   - Quality checking
   - Rate limiting

## What This MCP Does NOT Do

❌ Production database access (it's a template)
❌ Unrelated features outside of MCP server functionality
❌ Entertainment or non-MCP features

## When to Report Issues

### ✅ Valid Bug Reports
- Template code not working
- Configuration issues
- Authentication problems
- Feedback system errors

### ✅ Valid Feature Requests
- Additional template examples
- Better documentation
- New middleware patterns
- Enhanced configuration options

### ❌ Invalid Requests
- Features unrelated to MCP server development
- Jokes or test submissions
- Off-topic suggestions

## Example Valid Feedback

- "Auto-discovery not loading custom tools"
- "Add example of streaming tool responses"
- "Include TypeScript types for configuration"
- "Authentication middleware returns 500 error"

## Example Invalid Feedback

- "Add lyrics to responses" (not MCP-related)
- "Order pizza" (joke/absurd)
- "Make it better" (too vague)
- "Doesn't work" (no details)
"""
