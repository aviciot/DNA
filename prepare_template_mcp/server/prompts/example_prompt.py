"""
Example Prompt - Code Review
============================
Demonstrates proper prompt implementation with correct return format
"""

from mcp_app import mcp


@mcp.prompt()
def code_review(language: str = "python") -> str:
    """
    Generate a code review prompt for the specified language
    
    Args:
        language: Programming language (default: python)
    
    Returns:
        str: The prompt text
    """
    prompt = f"""You are an expert {language.title()} code reviewer. Please review the following code for:

1. **Code Quality**
   - Readability and maintainability
   - Proper naming conventions
   - Code organization

2. **Best Practices**
   - Following {language.title()} idioms
   - Error handling
   - Security considerations

3. **Performance**
   - Efficiency issues
   - Potential bottlenecks

4. **Documentation**
   - Comments and docstrings
   - Clear explanations

Please provide specific, actionable feedback with examples where appropriate.
"""
    
    # Return string directly - FastMCP handles the response format
    return prompt
