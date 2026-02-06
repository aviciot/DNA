# Template MCP - Technical Specification
## For LLM-Assisted Development

**Version**: 2.0.0  
**Last Updated**: January 6, 2026

---

## 📋 Overview

This document defines the **exact patterns and structure** to follow when creating new MCP servers using this template. When an LLM is asked to create a new MCP (e.g., "Create Salesforce MCP"), this spec ensures consistency and correctness.

**NEW in v2.0**:
- ✅ Knowledge base system for LLM-accessible documentation
- ✅ Traefik gateway integration patterns
- ✅ Enhanced README structure
- ✅ Help tools for runtime documentation access

---

## 🏗️ Project Structure (MANDATORY)

```
your_mcp/
├── server/
│   ├── __init__.py                    # Empty file
│   ├── config.py                      # Configuration loader (MODULE, not package) ⭐ BASE TEMPLATE
│   ├── server.py                      # Starlette app + middleware ⭐ BASE TEMPLATE
│   ├── mcp_app.py                     # FastMCP instance (MINIMAL - no tool logic) ⭐ BASE TEMPLATE
│   │
│   ├── config/                        # Configuration directory
│   │   ├── settings.yaml              # Default config 📝 CUSTOMIZE
│   │   ├── settings.dev.yaml          # Development config (optional) 📝 CUSTOMIZE
│   │   └── settings.prod.yaml         # Production config (optional) 📝 CUSTOMIZE
│   │
│   ├── knowledge_base/                # 🆕 Documentation for LLMs
│   │   ├── README.md                  # Knowledge base guide
│   │   ├── _TEMPLATE_overview.md      # Template for overview
│   │   ├── _TEMPLATE_tool_doc.md      # Template for tool documentation
│   │   ├── overview.md                # 📝 CREATE: What this MCP does
│   │   ├── workflows.md               # 📝 CREATE: Step-by-step guides
│   │   ├── architecture.md            # 📝 CREATE: Internal design (with diagrams)
│   │   ├── troubleshooting.md         # 📝 CREATE: Common errors and fixes
│   │   └── tools/                     # Tool-specific documentation
│   │       └── tool_name.md           # 📝 CREATE: Per-tool docs
│   │
│   ├── tools/                         # MCP Tools
│   │   ├── __init__.py
│   │   ├── help_tools.py              # 🆕 Knowledge base access tools (INCLUDE)
│   │   └── *.py                       # 📝 CUSTOMIZE: Your tool files (auto-discovered)
│   │
│   ├── resources/                     # MCP Resources
│   │   ├── __init__.py
│   │   └── *.py                       # 📝 CUSTOMIZE: Resource files (auto-discovered)
│   │
│   ├── prompts/                       # MCP Prompts
│   │   ├── __init__.py
│   │   └── *.py                       # 📝 CUSTOMIZE: Prompt files (auto-discovered)
│   │
│   ├── db/                            # Database connectors (optional)
│   │   ├── __init__.py
│   │   └── *.py                       # 📝 CUSTOMIZE: Database connection logic
│   │
│   └── utils/                         # Utility modules ⭐ BASE TEMPLATE
│       ├── __init__.py
│       ├── import_utils.py            # Auto-discovery (extend if needed)
│       ├── config_validator.py        # Config validation (add custom validators)
│       ├── request_logging.py         # Request logging (customize format)
│       └── rate_limiting.py           # Rate limiting (optional)
│
├── tests/                             # Test files
│   ├── conftest.py                    # Pytest configuration
│   ├── test_*.py                      # Test files
│   └── requirements.txt               # Test dependencies
│
├── .env.example                       # Environment variables template
├── .gitignore                         # Git ignore rules
├── Dockerfile                         # Container definition
├── docker-compose.yml                 # Docker Compose config
├── LICENSE                            # MIT License
└── README.md                          # User documentation
```

---

## 🔧 Critical Rules (HARD REQUIREMENTS)

### ⚠️ READ THIS FIRST: Most Common Failure Point

**99% of MCP client failures** are caused by violating Rule #0 below. Before writing ANY code, read and understand this rule completely.

### 0. Tool and Prompt Decorator Pattern ⚠️ **#0 PRIORITY - ALWAYS USE EXPLICIT PARAMETERS**

**THE PROBLEM THAT CAUSED CLIENT FAILURES:**
Using empty decorators `@mcp.tool()` with `async def` and return type annotations causes MCP clients (mcpjam, Claude Desktop) to receive undefined/invalid output structures. The clients expect a specific format that only works with explicit decorator parameters.

**THE CORRECT PATTERN (ONLY ACCEPTABLE FORMAT):**

```python
# ✅ CORRECT - ALWAYS USE THIS PATTERN
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

**NEVER USE THESE PATTERNS (WILL BREAK MCP CLIENTS):**

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

**CRITICAL RULES:**
- ✅ MUST include explicit `name="..."` parameter in decorator
- ✅ MUST include explicit `description="..."` parameter in decorator
- ❌ NO `async` keyword on tool/prompt functions
- ❌ NO return type annotations (like `-> str`, `-> dict`, `-> list`)
- ✅ Use regular `def`, never `async def`
- ✅ Functions can call async code internally if needed (using `asyncio.run()`)
- ✅ Multiple tools/prompts CAN be grouped in one file by category
  - Example: `database_tools.py` with list_databases, query_database, get_schema
  - Example: `container_tools.py` with start_container, stop_container, restart_container
- ✅ Auto-discovery finds all `@mcp.tool()` and `@mcp.prompt()` decorated functions across all files

**WHY THIS MATTERS:**
MCP clients parse tool/prompt metadata from the decorator parameters. When decorators are empty or functions use async/return types, FastMCP's internal serialization produces output that clients can't parse, resulting in "invalid output" errors.

**FILE ORGANIZATION:**
You don't need one tool per file. Group related tools together:
- Good: `tools/database_operations.py` with 5 database tools
- Good: `tools/api_tools.py` with 3 API endpoint tools
- Okay but verbose: `tools/list_items.py`, `tools/create_item.py`, `tools/delete_item.py`

Auto-discovery will find and register all decorated functions regardless of how you organize files.

---

### 1. Environment Variable Handling ⚠️ **MOST CRITICAL - ALWAYS FOLLOW THIS**

**THE PROBLEM THAT CAUSED FAILURES:**
Environment variables are always strings. YAML `${}` expansion only works at load time and doesn't handle type conversion. If you don't check `os.getenv()` in Python code, environment variables will be IGNORED!

**THE CORRECT PATTERN (3-Layer Approach):**

#### Layer 1: YAML Config (settings.yaml) - Simple Defaults with Comments
```yaml
security:
  authentication:
    enabled: false  # Set AUTH_ENABLED=true in .env to enable
    bearer_token: ""  # Set AUTH_TOKEN in .env
server:
  port: 8000  # Set MCP_PORT in .env
```

**DO NOT use `${VAR}` syntax** - it only works at file load and can't convert types properly.

#### Layer 2: Python Code - Always Check os.getenv() FIRST
```python
import os

# Boolean from env var (string "true"/"false" -> bool)
auth_enabled = os.getenv('AUTH_ENABLED', '').lower() == 'true' if os.getenv('AUTH_ENABLED') else config.get('security', {}).get('authentication', {}).get('enabled', False)

# String from env var (with fallback)
token = os.getenv('AUTH_TOKEN', '') or config.get('security', {}).get('authentication', {}).get('bearer_token', '')

# Integer from env var
port = int(os.getenv('MCP_PORT', config.get('server', {}).get('port', 8000)))
```

#### Layer 3: Docker Compose - Pass Environment Variables
```yaml
environment:
  - AUTH_ENABLED=${AUTH_ENABLED:-false}
  - AUTH_TOKEN=${AUTH_TOKEN:-}
  - MCP_PORT=${MCP_PORT:-8000}
```

**WHY THIS PATTERN WORKS:**
- ✅ Environment variables override config at **runtime** (not load time)
- ✅ Type conversion happens in Python where it's **explicit**
- ✅ Config file provides **documented defaults**
- ✅ Works in Docker, local dev, and production consistently
- ✅ No surprises - if env var is set, it WILL be used

**COMMON MISTAKES TO AVOID:**
- ❌ Using `${}` in YAML for booleans/integers (only works for strings at load time)
- ❌ Reading config dict without checking `os.getenv()` first
- ❌ Assuming YAML expansion will handle type conversion
- ❌ Not documenting env vars in comments

---

### 2. Import Strategy ⚠️

**RULE**: Use **absolute imports only** (no relative imports)

```python
# ❌ WRONG
from .config import get_config
from ..utils import helper

# ✅ CORRECT
from config import get_config
from utils import helper
```

**Why**: FastMCP runs with `uvicorn server:app`, treating files as scripts, not packages.

---

### 3. Config Module vs Package ⚠️

**RULE**: `config.py` is a **MODULE** (file), not a package (folder)

```
server/
├── config.py              # ✅ CORRECT - This is what you want
└── config/
    └── settings.yaml

# NOT this:
server/
└── config/               # ❌ WRONG - Don't create config/__init__.py
    ├── __init__.py
    └── settings.yaml
```

---

### 4. FastMCP 2.x API ⚠️

**RULE**: Use FastMCP 2.x API (not 0.x)

```python
# ✅ CORRECT - FastMCP 2.x
from fastmcp import FastMCP

mcp = FastMCP(name="your-mcp")  # Only 'name' parameter
mcp_http_app = mcp.http_app()   # Get ASGI app for mounting

@mcp.tool()
async def my_tool(...): ...

@mcp.resource("scheme://name")
async def my_resource(): ...

@mcp.prompt()
def my_prompt(): ...

# Mount in Starlette server.py:
app.mount('/', mcp_http_app)
```

```python
# ❌ WRONG - FastMCP 0.x (deprecated)
mcp = FastMCP(
    name="...",
    version="...",      # Not supported in 2.x
    description="..."   # Not supported in 2.x
)

# ❌ WRONG - Accessing internal _mcp_server
app.mount('/', mcp._mcp_server)  # NEVER DO THIS!

@mcp.resource("name")   # Missing scheme:// in 2.x
@mcp.prompt("name")     # Use function name in 2.x
```

**CRITICAL**: Always use `mcp.http_app()` method, **NEVER** access `_mcp_server` directly!

---

## 📝 File Templates

### mcp_app.py Template

```python
"""
Your MCP Application - FastMCP Instance
=======================================
Main MCP server using FastMCP framework
"""

import logging
from fastmcp import FastMCP

from config import get_config

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
config = get_config()

# Create FastMCP instance
mcp = FastMCP(
    name=config.get('mcp.name', 'your-mcp')
)

logger.info(f"Initializing {mcp.name}")
```

**CRITICAL**: Keep mcp_app.py minimal - NO tool logic here, only the FastMCP instance.

### Tool Template

```python
"""
Tool Description
================
What this tool does
"""

import logging
from mcp_app import mcp

logger = logging.getLogger(__name__)


@mcp.tool()
async def tool_name(param1: str, param2: int = 10) -> str:
    """
    Brief description for Claude
    
    Args:
        param1: Description
        param2: Description (default: 10)
    
    Returns:
        str: Description of return value
    """
    try:
        # 1. Validate inputs
        if not param1:
            return "Error: param1 cannot be empty"
        
        if param2 < 1:
            return "Error: param2 must be positive"
        
        # 2. Execute logic
        result = f"Processed: {param1} x {param2}"
        
        # 3. Return result (FastMCP handles response format)
        return result
        
    except Exception as e:
        # Log full error
        logger.exception(f"Error in tool_name: {e}")
        
        # Return user-friendly message
        return "Error: An unexpected error occurred"
```

**Pattern**: Always include try/except, input validation, and user-friendly errors.

### Resource Template

```python
"""
Resource Description
===================
What this resource provides
"""

import logging
from mcp_app import mcp

logger = logging.getLogger(__name__)


@mcp.resource("scheme://resource-name")
async def resource_name() -> str:
    """
    Brief description for Claude
    
    Returns:
        str: Resource content
    """
    try:
        # Generate resource content
        content = "Resource data here"
        
        return content
        
    except Exception as e:
        logger.exception(f"Error in resource_name: {e}")
        return "Error loading resource"
```

**Pattern**: Use proper URI scheme (e.g., `info://`, `data://`, `config://`)

### Prompt Template

```python
"""
Prompt Description
==================
What this prompt does
"""

import logging
from mcp_app import mcp

logger = logging.getLogger(__name__)


@mcp.prompt()
def prompt_name(context: str = "") -> str:
    """
    Brief description
    
    Args:
        context: Optional context
    
    Returns:
        str: Prompt text
    """
    prompt = f"""You are an expert assistant.

Context: {context}

Your task is to...
"""
    
    return prompt
```

---

## ⚙️ Configuration Pattern

### settings.yaml Structure

```yaml
# Server Configuration
server:
  version: "1.0.0"
  host: "0.0.0.0"
  port: ${MCP_PORT:-8100}

# MCP Configuration
mcp:
  name: "your-mcp"
  description: "Description of your MCP"

# Security Configuration
security:
  authentication:
    enabled: false
    bearer_token: ""

# Logging
logging:
  level: "INFO"
  format: "text"  # text or json

# Your custom configuration below
# ================================
```

### Environment-Specific Configs

- **settings.yaml**: Default configuration
- **settings.dev.yaml**: Development overrides (port 8200, auth disabled, debug logging)
- **settings.prod.yaml**: Production overrides (auth required, JSON logs, info level)

Load via `ENV` environment variable:
```bash
ENV=dev   # Loads settings.dev.yaml
ENV=prod  # Loads settings.prod.yaml
ENV=default  # Loads settings.yaml (or omit)
```

---

## 🔐 Authentication Patterns

### Bearer Token (Primary)

```python
# In requests:
Authorization: Bearer <token>

# In .env:
AUTH_ENABLED=true
AUTH_TOKEN=your-secret-token-32-chars-minimum
```

### API Key (Alternative)

```python
# In requests:
X-API-Key: <key>

# Implement in AuthenticationMiddleware
```

### Basic Auth (Alternative)

```python
# In requests:
Authorization: Basic <base64(user:pass)>

# Implement in AuthenticationMiddleware
```

---

## 🧪 Testing Pattern

### Test File Structure

```python
"""
Tests for your_tool
===================
"""

import pytest
from tools.your_tool import your_function


class TestYourTool:
    """Test cases for your tool"""
    
    @pytest.mark.asyncio
    async def test_basic_case(self):
        """Test basic functionality"""
        result = await your_function("input")
        assert result == "expected"
    
    @pytest.mark.asyncio
    async def test_validation_error(self):
        """Test input validation"""
        result = await your_function("")
        assert "Error" in result
```

### Running Tests

```bash
cd your_mcp
pip install -r tests/requirements.txt
pytest tests/ -v
```

---

## 🐳 Docker Pattern

### Dockerfile Structure

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY server/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy server code
COPY server/ .

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
```

**IMPORTANT**: Use `uv` instead of `pip` for faster, more reliable dependency installation.

### docker-compose.yml Structure

```yaml
version: '3.8'

services:
  your_mcp:
    build: .
    container_name: your_mcp
    ports:
      - "${MCP_PORT:-8100}:8000"
    environment:
      - MCP_PORT=8000
      - ENV=${ENV:-default}
      - AUTH_ENABLED=${AUTH_ENABLED:-false}
      - AUTH_TOKEN=${AUTH_TOKEN:-}
      - AUTO_DISCOVER=${AUTO_DISCOVER:-true}
    volumes:
      - ./server:/app:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

---

## 📊 Logging Standards

### Log Levels

- **DEBUG**: Detailed diagnostic info (development only)
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages (non-critical issues)
- **ERROR**: Error messages (critical issues)

### Log Format

**Text** (development):
```
2026-01-01 10:00:00,000 - module_name - INFO - Message here
```

**JSON** (production):
```json
{
  "timestamp": "2026-01-01T10:00:00.000Z",
  "level": "INFO",
  "module": "module_name",
  "message": "Message here",
  "correlation_id": "abc123"
}
```

---

## 🚦 Health Check Endpoints

### /healthz (Simple)
- Returns 200 OK if server is running
- No dependency checks
- Fast response

### /health/deep (Comprehensive)
- Checks database connections
- Checks external API availability
- Returns 200 if all healthy, 503 if any unhealthy
- Response includes check details

---

## 🔄 Auto-Discovery Behavior

When `AUTO_DISCOVER=true`:
1. Server scans `tools/`, `resources/`, `prompts/` directories
2. Imports all `.py` files (except `__init__.py` and files starting with `_`)
3. `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()` decorators auto-register
4. Logs each loaded module: `✅ Loaded: tools.your_tool`

When `AUTO_DISCOVER=false`:
- Falls back to static imports
- Useful for debugging or strict control

---

## 📚 Database Connection Pattern

If your MCP needs a database:

1. Create connector in `db/connector.py`
2. Use connection pooling (asyncpg, aiomysql, oracledb)
3. Initialize in `server.py` startup
4. Pass to tools via dependency injection or global instance
5. Add health check in `/health/deep`

Example:
```python
# db/connector.py
class DatabaseConnector:
    async def connect(self): ...
    async def execute_query(self, sql, params): ...
    async def health_check(self): ...

# server.py
from db.connector import db
await db.connect()  # In startup

# tools/query_tool.py
from db.connector import db

@mcp.tool()
async def query_data():
    rows = await db.execute_query("SELECT * FROM table")
    return rows
```

---

## ✅ Validation Checklist

Before deploying a new MCP, verify:

- [ ] All imports are absolute (no relative imports)
- [ ] `config.py` is a module (not `config/__init__.py`)
- [ ] FastMCP uses only `name` parameter
- [ ] Resources use `scheme://name` format
- [ ] Prompts use function names (not decorator parameters)
- [ ] All tools have error handling (try/except)
- [ ] All tools validate inputs
- [ ] Configuration validation runs on startup
- [ ] Health check endpoint works
- [ ] Docker container builds and runs
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Environment variables documented in `.env.example`
- [ ] README updated with project-specific info

---

## 🚀 Quick Start for LLMs

When asked to create a new MCP:

1. **Clone structure** from template_mcp
2. **Rename** `template-mcp` → `your-mcp` everywhere
3. **Update** `settings.yaml` with your MCP name
4. **Set up knowledge base** by copying templates:
   - `cp server/knowledge_base/_TEMPLATE_overview.md server/knowledge_base/overview.md`
   - Edit `overview.md` and customize all [CUSTOMIZE] sections
   - For each tool, create `server/knowledge_base/tools/tool_name.md`
5. **Create tools** in `tools/` following tool template
6. **Create resources** in `resources/` following resource template
7. **Create prompts** in `prompts/` following prompt template
8. **Add database** connector in `db/` if needed
9. **Configure Traefik** if using gateway:
   - Set `USE_TRAEFIK=true` in `.env`
   - Uncomment Traefik labels in `docker-compose.yml`
   - Uncomment `mcp_network` in `docker-compose.yml`
10. **Write tests** in `tests/` for each tool
11. **Update README** with your MCP description
12. **Test**: `docker-compose up -d` and verify `/healthz`

---

## 📚 Knowledge Base System (NEW in v2.0)

### What is it?

The knowledge base provides **LLM-queryable documentation** that lives with your code. LLMs can read this documentation at runtime to understand how to use your MCP.

### Why Use It?

- ✅ **Never goes stale** - Documentation updates with code changes
- ✅ **LLM-accessible** - Built-in help tools for querying docs
- ✅ **Maintainable** - Just edit markdown files
- ✅ **Version-controlled** - Docs live in git with code

### Required Files

Create these files in `server/knowledge_base/`:

1. **`overview.md`** (Copy from `_TEMPLATE_overview.md`)
   - What your MCP does
   - When to use it
   - Available tools list
   - Security and authentication
   - Configuration requirements

2. **`workflows.md`** (Create manually)
   - Step-by-step task guides
   - Common workflows
   - Example conversations
   - Tool combination patterns

3. **`architecture.md`** (Create manually)
   - How the MCP works internally
   - Data flow diagrams (use Mermaid!)
   - Configuration impact
   - Performance characteristics

4. **`troubleshooting.md`** (Create manually)
   - Common errors and messages
   - Causes and solutions
   - Debugging tips
   - FAQ

5. **`tools/tool_name.md`** (Copy from `_TEMPLATE_tool_doc.md` for each tool)
   - Input parameters with examples
   - Output structure
   - Usage examples
   - Real-world scenarios
   - Error handling

### Help Tools Pattern

**ALWAYS include `help_tools.py`** in your MCP:

```python
# server/tools/help_tools.py
from pathlib import Path
from mcp_app import mcp

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"

def read_knowledge_file(filename: str) -> str:
    """Read markdown file from knowledge_base directory"""
    filepath = KNOWLEDGE_BASE_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding='utf-8')
    return f"❌ File not found: {filename}"

@mcp.tool(
    name="list_knowledge_base_topics",
    description="📚 List all available documentation topics"
)
def list_knowledge_base_topics():
    # Implementation here
    pass

@mcp.tool(
    name="get_knowledge_base_content",
    description="📖 Get documentation from knowledge base"
)
def get_knowledge_base_content(topic: str = "overview"):
    # Implementation here
    pass
```

See the template's `server/tools/help_tools.py` for complete implementation.

### Documentation Best Practices

1. **Be specific** - Include actual examples, not placeholders
2. **Add diagrams** - Use Mermaid for architecture/flow diagrams
3. **Real errors** - Document actual error messages users will see
4. **Update regularly** - Keep docs in sync with code changes
5. **User-focused** - Write for LLM consumption, not developers

---

## 🌐 Traefik Gateway Integration (NEW in v2.0)

### What is Traefik Integration?

Traefik allows multiple MCPs to be accessed through a **single gateway** with **path-based routing**:
- Without Traefik: `http://localhost:8100/` (each MCP on different port)
- With Traefik: `http://localhost:8000/mcp-name/` (all MCPs on one gateway)

### When to Use Traefik

✅ **Use Traefik when:**
- Running multiple MCPs that need unified access
- Need load balancing across MCP instances
- Want centralized TLS termination
- Building production multi-MCP architecture

❌ **Skip Traefik when:**
- Running single MCP
- Development/testing locally
- Simple standalone deployment

### Configuration Pattern

#### 1. Environment Variables (.env)

```bash
# Basic MCP Configuration
MCP_CONTAINER_NAME=my_mcp
MCP_NAME=my-mcp              # Used in URL path
MCP_PORT=8100                 # External port (when NOT using Traefik)

# Traefik Configuration
USE_TRAEFIK=false             # Set to 'true' to enable
TRAEFIK_ENTRYPOINT=web        # Usually 'web' for HTTP
TRAEFIK_PATH_PREFIX=/my-mcp   # Gateway routes this path to your MCP
```

#### 2. Docker Compose (docker-compose.yml)

The template includes **commented Traefik labels**. To enable:

**Without Traefik (Default)**:
```yaml
services:
  my_mcp:
    ports:
      - "${MCP_PORT:-8100}:8000"  # Direct port binding
    networks:
      - default
```

**With Traefik (Uncomment labels)**:
```yaml
services:
  my_mcp:
    # ports:  # Comment out direct port binding
    #   - "${MCP_PORT:-8100}:8000"
    
    networks:
      - mcp_network  # Uncomment this
    
    labels:  # Uncomment all these labels
      - "traefik.enable=true"
      - "traefik.http.routers.${MCP_NAME}.rule=PathPrefix(`/${MCP_NAME}`)"
      - "traefik.http.routers.${MCP_NAME}.entrypoints=web"
      - "traefik.http.middlewares.${MCP_NAME}-stripprefix.stripprefix.prefixes=/${MCP_NAME}"
      - "traefik.http.routers.${MCP_NAME}.middlewares=${MCP_NAME}-stripprefix"
      - "traefik.http.services.${MCP_NAME}.loadbalancer.server.port=8000"
      - "traefik.http.services.${MCP_NAME}.loadbalancer.healthcheck.path=/healthz"

networks:
  # mcp_network:  # Uncomment when using Traefik
  #   external: true
  #   name: mcp_network
```

#### 3. Pattern to Follow

When an LLM creates a new MCP:

1. **Ask the user**: "Will this MCP use a Traefik gateway?"
   
2. **If YES**:
   - Set `USE_TRAEFIK=true` in `.env`
   - Set `MCP_NAME` to unique identifier (e.g., `salesforce-mcp`)
   - In `docker-compose.yml`:
     - Comment out `ports:` section
     - Uncomment all `labels:` lines
     - Uncomment `mcp_network` in `networks:`

3. **If NO** (default):
   - Leave `USE_TRAEFIK=false`
   - Keep `ports:` section active
   - Keep labels commented
   - Use default network

### Access Patterns

```bash
# Without Traefik
curl http://localhost:8100/healthz
curl http://localhost:8100/mcp

# With Traefik (assuming MCP_NAME=my-mcp)
curl http://localhost:8000/my-mcp/healthz
curl http://localhost:8000/my-mcp/mcp
```

### Important Notes

1. **PathPrefix stripping**: The `stripprefix` middleware removes `/mcp-name` before forwarding to your MCP, so your MCP still sees requests at root `/`

2. **Health checks**: Traefik automatically monitors `/healthz` and removes unhealthy instances from load balancing

3. **Network requirement**: MCPs using Traefik must join the `mcp_network` which should be created by the gateway

4. **Port conflicts**: When using Traefik, don't expose ports directly - gateway handles all routing

---

## 🎯 Common Mistakes to Avoid

1. ❌ Using relative imports
2. ❌ Creating `config/__init__.py`
3. ❌ Using FastMCP 0.x API
4. ❌ Forgetting error handling in tools
5. ❌ Not validating tool inputs
6. ❌ Exposing stack traces to users
7. ❌ Missing correlation IDs in logs
8. ❌ Not testing tools
9. ❌ Hardcoding configuration (use config.get())
10. ❌ Missing health checks
11. ❌ **NEW**: Skipping knowledge base setup
12. ❌ **NEW**: Modifying core files (server.py, mcp_app.py, config.py)
13. ❌ **NEW**: Enabling Traefik without uncommenting network
14. ❌ **NEW**: Not documenting tools in knowledge base

---

## 📞 Support

For questions or issues, refer to:
- FastMCP 2.x documentation
- This template's README.md
- Example implementations in the template
- Knowledge base templates in `server/knowledge_base/`

---

**End of Specification**
