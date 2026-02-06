# MCP Template Development Rules
## Rules for LLM-Assisted MCP Development

**Version**: 2.1.0  
**Last Updated**: February 4, 2026

---

## 🎯 Purpose

This document defines **mandatory rules** that LLMs MUST follow when helping developers create or modify MCP servers based on this template. These rules prevent common errors and ensure consistency.

---

## 🔴 CRITICAL RULE #0: Tool and Prompt Decorator Pattern

### ⚠️ THE MOST IMPORTANT RULE - ALWAYS FOLLOW THIS

**THE PROBLEM**: Using empty decorators `@mcp.tool()` with `async def` and return type annotations causes MCP clients (Claude Desktop, mcpjam) to receive undefined/invalid output structures.

### ✅ CORRECT PATTERN (ONLY ACCEPTABLE FORMAT)

```python
from mcp_app import mcp

@mcp.tool(
    name="tool_name",
    description="Clear, detailed description of what this tool does and when to use it"
)
def tool_name(param1: str, param2: int = 10):
    """Docstring for internal documentation."""
    # Tool logic here
    return "result string"

@mcp.prompt(
    name="prompt_name",
    description="Clear description of what context/guidance this prompt provides"
)
def prompt_name(context: str):
    """Docstring for internal documentation."""
    return f"""Prompt template text for {context}"""
```

### ❌ NEVER USE THESE PATTERNS (WILL BREAK MCP CLIENTS)

```python
# ❌ WRONG - Empty decorator
@mcp.tool()
async def tool_name(param: str) -> str:
    return result

# ❌ WRONG - Missing explicit name/description
@mcp.tool()
def tool_name(param: str):
    return result

# ❌ WRONG - Using async keyword
@mcp.tool(name="tool_name", description="...")
async def tool_name(param: str):
    return result

# ❌ WRONG - Using return type annotation
@mcp.tool(name="tool_name", description="...")
def tool_name(param: str) -> str:
    return result
```

### 📋 MANDATORY CHECKLIST

Before creating ANY tool or prompt, verify:

- ✅ Decorator has explicit `name="..."` parameter
- ✅ Decorator has explicit `description="..."` parameter  
- ✅ Function uses `def`, NOT `async def`
- ✅ NO return type annotations (no `-> str`, `-> dict`, etc.)
- ✅ Function can call async code internally if needed (using `asyncio.run()`)

### 📦 File Organization

- ✅ Multiple related tools CAN be in one file
- ✅ Example: `database_tools.py` with `list_databases`, `query_database`, `get_schema`
- ✅ Auto-discovery finds all `@mcp.tool()` decorated functions in all Python files

---

## 🔴 CRITICAL RULE #1: Environment Variable Handling

### ⚠️ THE PROBLEM

Environment variables are always strings. YAML `${}` expansion only works at load time and can't handle type conversion. If you don't check `os.getenv()` in Python, environment variables will be IGNORED.

### ✅ CORRECT PATTERN (3-Layer Approach)

#### Layer 1: YAML Config (settings.yaml) - Simple Defaults with Comments

```yaml
security:
  authentication:
    enabled: false  # Set AUTH_ENABLED=true in .env to enable
    bearer_token: ""  # Set AUTH_TOKEN in .env

server:
  port: 8000  # Set MCP_PORT in .env
```

**DO NOT use `${VAR}` syntax** - it only works at file load and can't convert types.

#### Layer 2: Python Code - Always Check os.getenv() FIRST

```python
import os
from config import get_config

config = get_config()

# Boolean from env var (string "true"/"false" -> bool)
auth_enabled = (
    os.getenv('AUTH_ENABLED', '').lower() == 'true' 
    if os.getenv('AUTH_ENABLED') 
    else config.get('security.authentication.enabled', False)
)

# String from env var (with fallback)
token = os.getenv('AUTH_TOKEN', '') or config.get('security.authentication.bearer_token', '')

# Integer from env var
port = int(os.getenv('MCP_PORT', config.get('server.port', 8000)))
```

#### Layer 3: Docker Compose - Pass Environment Variables

```yaml
environment:
  - AUTH_ENABLED=${AUTH_ENABLED:-false}
  - AUTH_TOKEN=${AUTH_TOKEN:-}
  - MCP_PORT=${MCP_PORT:-8000}
```

### 📋 MANDATORY RULES

- ✅ ALWAYS check `os.getenv()` BEFORE reading config dict
- ✅ Handle type conversion explicitly in Python
- ✅ Use config file for documented defaults
- ✅ Document env vars in comments
- ❌ NEVER rely on YAML `${}` for booleans or integers

---

## 🔴 CRITICAL RULE #2: Import Strategy

### ✅ CORRECT - Absolute Imports Only

```python
# ✅ CORRECT
from config import get_config
from utils.import_utils import import_submodules
from mcp_app import mcp
```

### ❌ WRONG - Relative Imports

```python
# ❌ WRONG - Will fail in FastMCP
from .config import get_config
from ..utils import helper
```

### 📋 WHY

FastMCP runs with `uvicorn server:app`, treating files as scripts, not packages. Relative imports fail in this context.

---

## 🔴 CRITICAL RULE #3: Config Module Structure

### ✅ CORRECT Structure

```
server/
├── config.py              # ✅ MODULE (file)
└── config/
    ├── settings.yaml
    ├── settings.dev.yaml
    └── settings.prod.yaml
```

### ❌ WRONG Structure

```
server/
└── config/               # ❌ PACKAGE (with __init__.py)
    ├── __init__.py
    └── settings.yaml
```

### 📋 MANDATORY RULE

- ✅ `config.py` is a MODULE (file), not a package (folder)
- ✅ Configuration YAML files go in `server/config/` directory
- ❌ NEVER create `config/__init__.py`

---

## 🔴 CRITICAL RULE #4: FastMCP 2.x API

### ✅ CORRECT - FastMCP 2.x Patterns

```python
from fastmcp import FastMCP

# Initialize (name parameter only)
mcp = FastMCP(name="your-mcp")

# Get ASGI app for mounting
mcp_http_app = mcp.http_app()

# In server.py, mount it
app.mount('/', mcp_http_app)

# Tools
@mcp.tool(name="...", description="...")
def my_tool(...): ...

# Resources (must have scheme://)
@mcp.resource("scheme://name")
def my_resource(): ...

# Prompts (use function name)
@mcp.prompt(name="...", description="...")
def my_prompt(): ...
```

### ❌ WRONG - FastMCP 0.x or Bad Patterns

```python
# ❌ WRONG - 0.x style initialization
mcp = FastMCP(
    name="...",
    version="...",      # Not supported in 2.x
    description="..."   # Not supported in 2.x
)

# ❌ WRONG - Accessing internal _mcp_server
app.mount('/', mcp._mcp_server)  # NEVER!

# ❌ WRONG - Resources without scheme
@mcp.resource("name")  # Missing scheme://

# ❌ WRONG - Old prompt style
@mcp.prompt("name")  # Use named parameter
```

---

## 🟡 IMPORTANT RULE #5: Auto-Discovery System

### How It Works

The template automatically discovers and imports all tools/resources/prompts:

```
server/
├── tools/
│   ├── __init__.py
│   ├── help_tools.py      # ✅ Auto-discovered
│   ├── database_tools.py  # ✅ Auto-discovered
│   └── api_tools.py       # ✅ Auto-discovered
├── resources/
│   └── *.py               # ✅ Auto-discovered
└── prompts/
    └── *.py               # ✅ Auto-discovered
```

### 📋 RULES

- ✅ Put tools in `server/tools/*.py` (excluding `__init__.py`)
- ✅ Put resources in `server/resources/*.py`
- ✅ Put prompts in `server/prompts/*.py`
- ✅ Use `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()` decorators
- ✅ Files are imported automatically at startup
- ❌ DON'T manually import tool files in server.py

### Disabling Auto-Discovery (Not Recommended)

Set `AUTO_DISCOVER=false` in .env, then manually import:

```python
# In server.py
from tools import database_tools
from tools import api_tools
```

---

## 🟡 IMPORTANT RULE #6: Error Handling Pattern

### ✅ CORRECT Pattern

```python
import logging
from mcp_app import mcp

logger = logging.getLogger(__name__)

@mcp.tool(
    name="my_tool",
    description="Description of what tool does"
)
def my_tool(param: str):
    """Tool implementation."""
    try:
        # 1. Validate inputs
        if not param:
            return "Error: param is required"
        
        if not isinstance(param, str):
            return f"Error: param must be string, got {type(param).__name__}"
        
        # 2. Execute logic
        result = do_something(param)
        
        # 3. Return result (string, dict, or list)
        return {
            "status": "success",
            "data": result,
            "message": "Operation completed"
        }
        
    except ValueError as e:
        # Handle known errors with user-friendly messages
        logger.warning(f"Validation error in my_tool: {e}")
        return f"Error: {str(e)}"
        
    except Exception as e:
        # Log unexpected errors, but don't expose internals
        logger.exception(f"Unexpected error in my_tool: {e}")
        return "Error: An unexpected error occurred. Please contact support."
```

### 📋 MANDATORY CHECKLIST

- ✅ Validate ALL inputs
- ✅ Use try/except blocks
- ✅ Log errors with context
- ✅ Return user-friendly error messages
- ✅ DON'T expose stack traces or internals to users
- ✅ Use specific exception types when possible

---

## 🟡 IMPORTANT RULE #7: Logging Standards

### ✅ CORRECT Logging Pattern

```python
import logging

# At module level
logger = logging.getLogger(__name__)

# In functions
def my_function():
    logger.info("Starting operation")
    logger.debug(f"Processing with param={value}")
    logger.warning("Something unusual happened")
    logger.error(f"Operation failed: {error}")
    logger.exception("Unexpected error occurred")  # Includes stack trace
```

### 📋 Log Level Guidelines

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (tool called, operation completed)
- **WARNING**: Something unexpected but not breaking
- **ERROR**: Error occurred, operation failed
- **EXCEPTION**: Like ERROR but includes full stack trace

### 📋 RULES

- ✅ Use module-level logger: `logger = logging.getLogger(__name__)`
- ✅ Log tool invocations at INFO level
- ✅ Log errors at ERROR level
- ✅ Use `logger.exception()` for unexpected errors (includes stack trace)
- ❌ DON'T use print() statements
- ❌ DON'T log sensitive data (passwords, tokens, PII)

---

## 🟡 IMPORTANT RULE #8: Configuration Best Practices

### settings.yaml Structure

```yaml
# MCP Identity
mcp:
  name: "Your MCP Name"
  version: "1.0.0"
  description: "What your MCP does"

# Server Configuration
server:
  port: 8000
  host: "0.0.0.0"
  log_level: "INFO"

# Security
security:
  authentication:
    enabled: false
    bearer_token: ""
  rate_limiting:
    enabled: false
    requests_per_minute: 60

# Your Custom Sections
database:
  host: "localhost"
  port: 5432
  name: "mydb"

api:
  endpoint: "https://api.example.com"
  timeout: 30
```

### 📋 RULES

- ✅ Use clear section hierarchy
- ✅ Include comments explaining env var overrides
- ✅ Provide sensible defaults
- ✅ Keep sensitive values empty (set via env vars)
- ✅ Document all configuration options in README

---

## 🟡 IMPORTANT RULE #9: Knowledge Base System

### Purpose

Provide LLM-accessible documentation that's always up-to-date (read at runtime).

### Structure

```
server/knowledge_base/
├── README.md                 # Knowledge base guide
├── overview.md               # What MCP does, when to use
├── workflows.md              # Step-by-step guides
├── architecture.md           # How it works (with diagrams)
├── troubleshooting.md        # Common errors and fixes
└── tools/
    ├── tool_one.md          # Tool-specific documentation
    └── tool_two.md
```

### 📋 RULES

- ✅ Create `overview.md` explaining what MCP does
- ✅ Document each tool in `tools/tool_name.md`
- ✅ Use Mermaid diagrams for architecture
- ✅ Include examples and use cases
- ✅ Keep documentation in sync with code
- ✅ LLMs can query docs via `get_knowledge_base_content(topic="...")`

### Tool Documentation Template

```markdown
# Tool Name

## Purpose
What this tool does and why it exists.

## When to Use
Specific scenarios where this tool is appropriate.

## Parameters
- `param1` (type): Description
- `param2` (type, optional): Description, default value

## Returns
What the tool returns.

## Examples

### Example 1: Basic Usage
\`\`\`python
{
  "param1": "value",
  "param2": 123
}
\`\`\`

### Example 2: Advanced Usage
\`\`\`python
{
  "param1": "complex_value",
  "param2": 999
}
\`\`\`

## Error Handling
Common errors and how to resolve them.

## Notes
Additional information, limitations, tips.
```

---

## 🟡 IMPORTANT RULE #10: Testing Patterns

### Test File Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── test_tools.py            # Tool tests
├── test_resources.py        # Resource tests
├── test_prompts.py          # Prompt tests
├── test_config.py           # Configuration tests
└── requirements.txt         # Test dependencies
```

### Test Pattern Example

```python
# tests/test_tools.py
import pytest
from server.tools.example_tool import echo

def test_echo_basic():
    """Test basic echo functionality"""
    result = echo(message="Hello", repeat=1)
    assert result == "Hello"

def test_echo_repeat():
    """Test echo with repeat"""
    result = echo(message="Hi", repeat=3)
    assert result == "Hi\nHi\nHi"

def test_echo_validation():
    """Test input validation"""
    result = echo(message="", repeat=1)
    assert "Error" in result
    
def test_echo_repeat_limit():
    """Test repeat limit"""
    result = echo(message="Test", repeat=99)
    assert "Error" in result
```

### 📋 RULES

- ✅ Test tool logic independently (unit tests)
- ✅ Test error handling paths
- ✅ Test input validation
- ✅ Use pytest fixtures for setup/teardown
- ✅ Mock external dependencies (databases, APIs)
- ✅ Test both success and failure cases

---

## 🟢 RECOMMENDED RULE #11: Docker Best Practices

### Dockerfile Pattern

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (caching)
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY server/ ./server/
COPY .env .env

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Run with hot reload in dev
CMD ["uvicorn", "server.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### docker-compose.yml Pattern

```yaml
version: '3.8'

services:
  your-mcp:
    build: .
    container_name: ${MCP_CONTAINER_NAME:-your_mcp}
    ports:
      - "${MCP_PORT:-8000}:8000"
    environment:
      - AUTH_ENABLED=${AUTH_ENABLED:-false}
      - AUTH_TOKEN=${AUTH_TOKEN:-}
    volumes:
      - ./server:/app/server  # Hot reload
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 3s
      retries: 3
```

---

## 🟢 RECOMMENDED RULE #12: Traefik Integration (Optional)

### When to Use Traefik

- ✅ Running multiple MCPs
- ✅ Need centralized authentication
- ✅ Want path-based routing (e.g., `/mcp-name`)
- ✅ Need load balancing

### docker-compose.yml with Traefik

```yaml
services:
  your-mcp:
    build: .
    # Uncomment for Traefik:
    # labels:
    #   - "traefik.enable=true"
    #   - "traefik.http.routers.your-mcp.rule=PathPrefix(`/your-mcp`)"
    #   - "traefik.http.routers.your-mcp.entrypoints=web"
    #   - "traefik.http.services.your-mcp.loadbalancer.server.port=8000"
    #   - "traefik.http.middlewares.your-mcp-strip.stripprefix.prefixes=/your-mcp"
    #   - "traefik.http.routers.your-mcp.middlewares=your-mcp-strip"
    # networks:
    #   - mcp_network
    
    # Comment out for Traefik:
    ports:
      - "${MCP_PORT:-8000}:8000"

# Uncomment for Traefik:
# networks:
#   mcp_network:
#     external: true
```

---

## 📋 Pre-Development Checklist

Before creating/modifying an MCP, verify:

- [ ] Understand Rule #0 (tool/prompt decorators)
- [ ] Understand Rule #1 (environment variables)
- [ ] Know to use absolute imports (Rule #2)
- [ ] Understand config.py is a module, not package (Rule #3)
- [ ] Familiar with FastMCP 2.x API (Rule #4)
- [ ] Understand auto-discovery system (Rule #5)
- [ ] Know error handling pattern (Rule #6)
- [ ] Understand logging standards (Rule #7)

---

## 📋 Pre-Commit Checklist

Before committing code, verify:

- [ ] All tools use explicit `name=` and `description=` parameters
- [ ] No `async def` in tool/prompt functions
- [ ] No return type annotations in tool/prompt functions
- [ ] All imports are absolute (no relative imports)
- [ ] Environment variables checked with `os.getenv()` before config
- [ ] Error handling includes try/except blocks
- [ ] User-facing errors are friendly (no stack traces)
- [ ] All operations are logged appropriately
- [ ] Tests pass (if tests exist)
- [ ] Documentation updated (if behavior changed)

---

## 🚨 Common Mistakes to Avoid

### Mistake #1: Empty Decorators
```python
# ❌ WRONG
@mcp.tool()
def my_tool(): ...

# ✅ CORRECT
@mcp.tool(name="my_tool", description="...")
def my_tool(): ...
```

### Mistake #2: Async Functions
```python
# ❌ WRONG
@mcp.tool(name="...", description="...")
async def my_tool(): ...

# ✅ CORRECT
@mcp.tool(name="...", description="...")
def my_tool(): ...
```

### Mistake #3: Return Type Annotations
```python
# ❌ WRONG
@mcp.tool(name="...", description="...")
def my_tool() -> dict: ...

# ✅ CORRECT
@mcp.tool(name="...", description="...")
def my_tool(): ...
```

### Mistake #4: Relative Imports
```python
# ❌ WRONG
from .config import get_config

# ✅ CORRECT
from config import get_config
```

### Mistake #5: Ignoring Environment Variables
```python
# ❌ WRONG
auth_enabled = config.get('security.authentication.enabled')

# ✅ CORRECT
auth_enabled = (
    os.getenv('AUTH_ENABLED', '').lower() == 'true'
    if os.getenv('AUTH_ENABLED')
    else config.get('security.authentication.enabled', False)
)
```

---

## 📚 Quick Reference

### Tool Template
```python
@mcp.tool(
    name="tool_name",
    description="What it does and when to use it"
)
def tool_name(param: str, optional: int = 10):
    try:
        # Validate
        if not param:
            return "Error: param required"
        # Execute
        result = do_work(param)
        # Return
        return {"status": "success", "data": result}
    except Exception as e:
        logger.exception(f"Error: {e}")
        return "Error: Operation failed"
```

### Resource Template
```python
@mcp.resource("scheme://name")
def resource_name():
    return "Resource content"
```

### Prompt Template
```python
@mcp.prompt(
    name="prompt_name",
    description="What guidance it provides"
)
def prompt_name(context: str = "general"):
    return f"Prompt text for {context}"
```

---

## 🎯 Success Criteria

Your MCP implementation is correct when:

1. ✅ All tools follow Rule #0 (explicit decorators, no async, no return types)
2. ✅ Environment variables are checked before config values
3. ✅ All imports are absolute
4. ✅ Auto-discovery works (tools show up without manual imports)
5. ✅ Error handling is comprehensive and user-friendly
6. ✅ Logging provides good debugging information
7. ✅ Docker Compose setup works out of the box
8. ✅ Health checks respond correctly
9. ✅ Knowledge base documentation is complete
10. ✅ Tests pass (if tests exist)

---

**Remember**: When in doubt, refer to SPEC.md for detailed examples and patterns!

---

## 📋 APPENDIX: Using MCP_REQUIREMENTS_TEMPLATE.md

### For LLMs: How to Create MCP from Requirements

When a user provides a filled-out `MCP_REQUIREMENTS_TEMPLATE.md` file:

#### Step 1: Read All Documentation (In Order)

1. **MCP_REQUIREMENTS_TEMPLATE.md** - User's specific requirements
2. **This file (.amazonq/rules/mcp.md)** - Development rules
3. **SPEC.md** - Technical patterns and examples
4. **README.md** - Template features and setup

#### Step 2: Validate Requirements

Check that requirements document has:
- [ ] MCP name and description
- [ ] At least one tool defined
- [ ] External system connections (if any) fully specified
- [ ] Database requirements clear (yes/no, if yes: type, schema)
- [ ] Environment variables listed
- [ ] Configuration sections defined

#### Step 3: Implementation Order

Follow this sequence:

1. **Configuration Files**
   - Update `server/config/settings.yaml` with custom sections
   - Create `.env.example` with all required variables
   - Validate config structure

2. **Database Setup** (if required)
   - Choose appropriate driver (asyncpg, aiomysql, oracledb)
   - Update `requirements.txt`
   - Implement `server/db/connector.py`
   - Add database lifecycle to `server/server.py`
   - Create schema/migration files if specified
   - Add database health check

3. **Core Tools** (Priority: High → Medium → Low)
   - Implement each tool following **Rule #0** (explicit decorators, no async, no return types)
   - Add comprehensive error handling
   - Add input validation
   - Add logging
   - Test each tool as you go

4. **Resources** (if any)
   - Implement each resource
   - Follow resource URI patterns (`scheme://name`)

5. **Prompts** (if any)
   - Implement each prompt
   - Follow prompt patterns

6. **External System Connections**
   - Implement connectors/clients for external APIs
   - Add retry logic
   - Add health checks
   - Handle authentication properly

7. **Knowledge Base Documentation**
   - Copy templates from `knowledge_base/_TEMPLATE_*.md`
   - Fill in overview.md
   - Fill in workflows.md
   - Fill in architecture.md (add Mermaid diagrams)
   - Fill in troubleshooting.md
   - Create tool-specific docs in `knowledge_base/tools/`

8. **Testing**
   - Create test files in `tests/`
   - Test critical paths
   - Test error handling

9. **Docker & Deployment**
   - Update `docker-compose.yml` if database/services needed
   - Update `.env.example` with all variables
   - Test Docker build and run

#### Step 4: Quality Verification

Before marking complete, verify:

- [ ] **Rule #0 Compliance**: All tools have explicit `name=` and `description=`, no `async def`, no return type annotations
- [ ] **Environment Variables**: All env vars checked with `os.getenv()` before config
- [ ] **Error Handling**: Try/except in all tools, user-friendly messages
- [ ] **Logging**: Appropriate logging throughout, no sensitive data logged
- [ ] **Database** (if applicable): Proper connection pooling, health checks, parameterized queries
- [ ] **Documentation**: Knowledge base complete, clear examples
- [ ] **Configuration**: 3-layer pattern (YAML defaults, os.getenv(), Docker env vars)
- [ ] **Health Checks**: `/healthz` works, `/health/deep` includes all services
- [ ] **Docker**: Builds and runs successfully

#### Step 5: Document Deviations

If you had to deviate from requirements:
- Document why
- Explain the alternative approach
- Update knowledge base with clarification

### Example Implementation Flow

Given this requirement:

```markdown
## Tools

### Tool 1: list_github_repos

**Name**: `list_github_repos`
**Description**: List GitHub repositories for a user or organization
**Parameters**:
- `username` (string, required): GitHub username or org
- `type` (string, optional, default="all"): Filter (all, owner, member)
```

Implementation:

```python
# server/tools/github_tools.py
import logging
import asyncio
import httpx
import os
from mcp_app import mcp
from config import get_config

logger = logging.getLogger(__name__)

@mcp.tool(
    name="list_github_repos",
    description=(
        "List GitHub repositories for a user or organization.\n\n"
        "**Use when:** User asks to 'show repos', 'list repositories', "
        "or wants to see what repos exist.\n"
        "**Parameters:**\n"
        "  - username: GitHub username or organization name\n"
        "  - type: Filter by 'all', 'owner', or 'member'\n\n"
        "**Returns:** Dictionary with 'repositories' list and 'count'"
    )
)
def list_github_repos(username: str, type: str = "all"):
    """List GitHub repositories"""
    
    async def _fetch():
        try:
            # Validate inputs
            if not username:
                return {"error": "username is required"}
            
            if type not in ["all", "owner", "member"]:
                return {"error": f"type must be 'all', 'owner', or 'member', got '{type}'"}
            
            # Get GitHub token from env
            token = os.getenv('GITHUB_TOKEN')
            if not token:
                return {"error": "GITHUB_TOKEN not configured"}
            
            # Make API call
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            }
            
            url = f"https://api.github.com/users/{username}/repos"
            params = {"type": type, "per_page": 100}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                repos = response.json()
            
            logger.info(f"Listed {len(repos)} repositories for {username}")
            
            return {
                "status": "success",
                "count": len(repos),
                "repositories": [
                    {
                        "name": r["name"],
                        "full_name": r["full_name"],
                        "description": r["description"],
                        "url": r["html_url"],
                        "stars": r["stargazers_count"],
                        "language": r["language"]
                    }
                    for r in repos
                ]
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code}")
            return {"error": f"GitHub API error: {e.response.status_code}"}
        except Exception as e:
            logger.exception(f"Failed to list repos: {e}")
            return {"error": "Failed to list repositories"}
    
    return asyncio.run(_fetch())
```

Key points:
✅ Rule #0: Explicit name and description
✅ No `async def` (uses `def` with `asyncio.run()`)
✅ No return type annotation
✅ Comprehensive error handling
✅ Input validation
✅ Logging
✅ Environment variable for credentials

### Common Pitfalls to Avoid

1. **Forgetting Rule #0**: Most common mistake!
2. **Not checking `os.getenv()`**: Environment variables won't work
3. **Ignoring error handling**: Users will see stack traces
4. **Logging sensitive data**: Passwords, tokens in logs
5. **Not using parameterized queries**: SQL injection risk
6. **Skipping database health checks**: Hard to debug connection issues
7. **Incomplete documentation**: LLMs can't help users without docs

### Success Indicators

You've successfully created the MCP when:
- ✅ Docker builds without errors
- ✅ Server starts and shows all tools loaded
- ✅ `/healthz` returns OK
- ✅ `/health/deep` shows all services healthy
- ✅ All priority tools work correctly
- ✅ Knowledge base documentation is complete
- ✅ No Rule #0 violations

---

**Now you're ready to create MCPs from requirements!** 🚀
