# Template MCP Server

> **🎯 Purpose**: Production-ready base template for building MCP (Model Context Protocol) servers using FastMCP 2.x
> 
> **👥 Audience**: Developers creating new MCP servers, LLMs assisting with MCP development
>
> **📖 Complete Specification**: See [SPEC.md](SPEC.md) for detailed patterns and rules

---

## 📋 Table of Contents

- [What is This?](#what-is-this)
- [Two Ways to Use This Template](#two-ways-to-use-this-template)
- [Features](#features)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Creating Your MCP](#creating-your-mcp)
- [Database Setup (Optional)](#database-setup-optional)
- [Knowledge Base Setup](#knowledge-base-setup)
- [Feedback System (Optional)](#feedback-system-optional)
- [Traefik Gateway Integration](#traefik-gateway-integration)
- [Development Guide](#development-guide)
- [Testing](#testing)
- [Deployment](#deployment)
- [For LLMs](#for-llms)

---

## 🎯 What is This?

This is a **template repository** for creating MCP servers. It includes:

✅ **Hot-reload capable server.py** - Never manually restart during development  
✅ **Auto-discovery** - Tools/resources/prompts automatically loaded  
✅ **Structured logging** - Correlation IDs, request tracking, JSON output  
✅ **Knowledge base system** - Built-in help tools for LLM consumption  
✅ **Traefik-ready** - Optional gateway integration (commented labels)  
✅ **Production patterns** - Auth, rate limiting, health checks, graceful shutdown  

### 🔑 Key Principle

**Use core files as base templates** (server.py, mcp_app.py, config.py). These provide:
- Hot reload functionality
- Auto-discovery of tools
- Structured logging
- Request tracking

💡 **Modify them if you need to**, but they work well out-of-the-box for most cases.

**Always customize these**:
- `server/config/settings.yaml` - Your configuration
- `server/tools/*.py` - Your tools
- `server/knowledge_base/*.md` - Your documentation
- `docker-compose.yml` labels - Traefik if needed

---

## 🎨 Two Ways to Use This Template

### Option 1: Manual Development (Traditional)

1. Clone the template
2. Manually create tools one by one
3. Configure settings as needed
4. Write documentation

**Best for**: Developers who want full control and understand the codebase

### Option 2: LLM-Assisted Generation (Recommended!) 🤖

1. Fill out [MCP_REQUIREMENTS_TEMPLATE.md](MCP_REQUIREMENTS_TEMPLATE.md) with your requirements
2. Provide it to an LLM along with this template
3. LLM reads `.amazonq/rules/mcp.md` and `SPEC.md`
4. LLM generates complete MCP following all patterns and rules

**Best for**: Quickly creating new MCPs, ensuring consistency, following best practices

**Example workflow**:
```bash
# 1. Copy and fill out requirements
cp MCP_REQUIREMENTS_TEMPLATE.md MY_MCP_REQUIREMENTS.md
# Edit MY_MCP_REQUIREMENTS.md with your needs

# 2. Ask LLM to create MCP
"Using template_mcp, create an MCP based on MY_MCP_REQUIREMENTS.md.
Follow all rules in .amazonq/rules/mcp.md and patterns in SPEC.md."

# 3. LLM generates:
#    - All tools with correct Rule #0 patterns
#    - Database setup (if needed)
#    - Configuration files
#    - Knowledge base docs
#    - Docker setup
```

---

## ✨ Features

### Core Infrastructure
- ✅ **FastMCP 2.x** - Latest framework with proper SSE/HTTP support
- ✅ **Auto-Discovery** - Automatically loads all tools, resources, prompts
- ✅ **Hot Reload** - Code changes detected, server reloads (uvicorn --reload)
- ✅ **Request Logging** - Every request logged with correlation ID
- ✅ **Error Handling** - Comprehensive patterns in all tools

### Configuration & Validation
- ✅ **Config Validation** - Validates settings.yaml on startup (fail fast)
- ✅ **Multi-Environment** - Separate configs for dev/prod
- ✅ **Environment Variables** - .env support with template

### Security & Operations
- ✅ **Multiple Auth Methods** - Bearer token, API Key, Basic Auth
- ✅ **Health Checks** - `/healthz` (simple) and `/health/deep` (thorough)
- ✅ **Rate Limiting** - Optional middleware for API protection
- ✅ **Graceful Shutdown** - Handles SIGINT/SIGTERM properly

### Developer Experience
- ✅ **Knowledge Base System** - Built-in help tools for documentation
- ✅ **Testing Framework** - Pytest examples and patterns
- ✅ **Database Template** - Connection pooling pattern included
- ✅ **Structured Logging** - JSON or text format
- ✅ **Docker Ready** - Complete Docker setup with health checks

### Gateway Integration
- ✅ **Traefik-Ready** - Commented labels for easy gateway setup
- ✅ **Path-based Routing** - Each MCP gets /mcp-name prefix
- ✅ **Health Check Integration** - Load balancer health checks

### LLM Development
- ✅ **Comprehensive SPEC.md** - Complete patterns for LLM-assisted development
- ✅ **Template Files** - Knowledge base templates included
- ✅ **Clear Structure** - Predictable organization for code generation

### Optional Features
- ✅ **Feedback System** - User feedback with GitHub integration (disabled by default)
  - Interactive quality checking
  - Multi-level rate limiting
  - Admin dashboard for feedback management
  - See [FEEDBACK_SETUP_GUIDE.md](FEEDBACK_SETUP_GUIDE.md) for setup

---

## 🎓 How to Use This Template

### This is a Template, Not an Application

This repository is designed to be **cloned and customized** for your specific MCP needs. Think of it as a starting point that provides:

1. **Core Infrastructure** - Server setup, auto-discovery, logging (keep as-is or modify)
2. **Example Patterns** - Sample tool, resource, prompt (replace with yours)
3. **Documentation Templates** - Knowledge base structure (copy and customize)
4. **Development Rules** - LLM guidelines in `.amazonq/rules/mcp.md`

### Auto-Discovery Feature

One of the key features is **automatic tool/resource/prompt discovery**:

```
server/
├── tools/
│   ├── my_tool.py        ← Add your tool here
│   ├── another_tool.py   ← And another one
│   └── more_tools.py     ← As many as you need
```

**How it works:**
- On startup, server automatically imports all `*.py` files in `tools/`, `resources/`, `prompts/`
- Any function decorated with `@mcp.tool()`, `@mcp.resource()`, or `@mcp.prompt()` is registered
- No manual importing needed in `server.py`
- Multiple related tools can be in one file (e.g., `database_tools.py`)

**Benefits:**
- ✅ Add new tools by simply creating files
- ✅ No configuration changes needed
- ✅ Hot reload picks up changes automatically
- ✅ Clean organization by feature/domain

**Example:**
```python
# server/tools/my_custom_tool.py
from mcp_app import mcp

@mcp.tool(
    name="my_custom_tool",
    description="What this tool does"
)
def my_custom_tool(param: str):
    return f"Processed: {param}"
```

That's it! The tool is automatically discovered and available.

---

## 🚀 Quick Start

### 1. Clone the Template

```bash
git clone https://github.com/yourusername/template_mcp.git my-new-mcp
cd my-new-mcp
rm -rf .git  # Remove template git history
git init     # Start fresh
```

### 2. Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Key variables to customize**:
```bash
MCP_CONTAINER_NAME=my_mcp        # Docker container name
MCP_NAME=my-mcp                   # Service name (used in paths)
MCP_PORT=8100                     # External port
AUTH_ENABLED=false                # Enable auth if needed
USE_TRAEFIK=false                 # Set true if using gateway
```

### 3. Configure Your MCP

Edit `server/config/settings.yaml`:

```yaml
mcp:
  name: "My MCP Server"
  version: "1.0.0"
  description: "Description of what your MCP does"

# Add your custom configuration sections
database:
  host: "localhost"
  port: 5432
  
api:
  endpoint: "https://api.example.com"
  timeout: 30
```

### 4. Run with Docker

```bash
# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f

# Check health
curl http://localhost:8100/healthz
```

### 5. Verify It Works

```bash
# Simple health check
curl http://localhost:8100/healthz
# Expected: OK

# Deep health check
curl http://localhost:8100/health/deep
# Expected: JSON with detailed status

# Version info
curl http://localhost:8100/version
# Expected: JSON with version, tools count, etc.
```

---

## 📁 Project Structure

```
template_mcp/
├── .env.example                      # Environment variables template
├── .gitignore                        # Git ignore rules
├── docker-compose.yml                # Docker Compose (Traefik-ready)
├── Dockerfile                        # Container definition
├── LICENSE                           # MIT License
├── README.md                         # This file
├── SPEC.md                          # ⭐ Technical spec for LLMs
│
└── server/                          # Python application
    ├── __init__.py                  # Package marker
    ├── server.py                    # ⭐ BASE TEMPLATE (modify if needed)
    ├── mcp_app.py                   # ⭐ BASE TEMPLATE (modify if needed)
    ├── config.py                    # ⭐ BASE TEMPLATE (modify if needed)
    │
    ├── config/                      # Configuration files
    │   ├── settings.yaml            # 📝 CUSTOMIZE: Default config
    │   ├── settings.dev.yaml        # 📝 CUSTOMIZE: Dev overrides
    │   └── settings.prod.yaml       # 📝 CUSTOMIZE: Prod overrides
    │
    ├── knowledge_base/              # ⭐ Documentation for LLMs
    │   ├── README.md                # Knowledge base guide
    │   ├── _TEMPLATE_overview.md    # Template for overview
    │   ├── _TEMPLATE_tool_doc.md    # Template for tool docs
    │   └── tools/                   # Tool-specific documentation
    │
    ├── tools/                       # 📝 CUSTOMIZE: Your MCP tools
    │   ├── __init__.py              
    │   ├── help_tools.py            # Knowledge base access tools
    │   └── example_tool.py          # Example (replace with yours)
    │
    ├── resources/                   # 📝 CUSTOMIZE: Your MCP resources
    │   ├── __init__.py
    │   └── example_resource.py      # Example (replace with yours)
    │
    ├── prompts/                     # 📝 CUSTOMIZE: Your MCP prompts
    │   ├── __init__.py
    │   └── example_prompt.py        # Example (replace with yours)
    │
    ├── db/                          # 📝 OPTIONAL: Database connectors
    │   ├── __init__.py
    │   └── connector.py             # Database connection template
    │
    └── utils/                       # 🔒 CORE UTILITIES (DON'T MODIFY)
        ├── __init__.py
        ├── import_utils.py          # Auto-discovery system
        ├── config_validator.py      # Config validation
        ├── request_logging.py       # Request logging middleware
        └── rate_limiting.py         # Rate limiting (optional)
```

### File Legend
- ⭐ **BASE TEMPLATE** - Use as foundation, modify if needed
- 📝 **CUSTOMIZE** - Always edit these for your MCP
- 🔒 **UTILITIES** - Helper functions, extend as needed

---

## 🛠️ Creating Your MCP

### Step 1: Set Up Knowledge Base

The knowledge base provides LLM-accessible documentation:

```bash
cd server/knowledge_base

# 1. Create overview
cp _TEMPLATE_overview.md overview.md
nano overview.md  # Customize all [CUSTOMIZE] sections

# 2. Create tool documentation (for each tool)
cp _TEMPLATE_tool_doc.md tools/your_tool_name.md
nano tools/your_tool_name.md  # Fill in tool details
```

**What to document**:
- `overview.md` - What your MCP does, when to use it
- `workflows.md` - Step-by-step guides for common tasks
- `architecture.md` - How it works internally (add Mermaid diagrams!)
- `troubleshooting.md` - Common errors and solutions
- `tools/tool_name.md` - Each tool's detailed documentation

### Step 2: Create Your Tools

```python
# server/tools/my_first_tool.py
from mcp_app import mcp

@mcp.tool(
    name="my_first_tool",
    description=(
        "Clear description of what this tool does.\n\n"
        "**Use when:** Describe the scenario\n"
        "**Returns:** What the tool returns"
    )
)
def my_first_tool(param1: str, param2: int = 10):
    """Internal docstring for developers."""
    
    # Your tool logic here
    result = do_something(param1, param2)
    
    return {
        "status": "success",
        "data": result,
        "message": "Tool executed successfully"
    }
```

**✅ Critical**: Always use explicit `name` and `description` in decorators (see [SPEC.md](SPEC.md) Rule #0)

### Step 3: Add Resources (Optional)

```python
# server/resources/my_resource.py
from mcp_app import mcp

@mcp.resource(
    uri="info://my-resource",
    name="My Resource",
    description="Description of what this resource provides"
)
def my_resource():
    """Provide context or information."""
    return "Resource content here"
```

### Step 4: Add Prompts (Optional)

```python
# server/prompts/my_prompt.py
from mcp_app import mcp

@mcp.prompt(
    name="my_prompt",
    description="Description of what guidance this prompt provides"
)
def my_prompt(context: str):
    """Provide contextual guidance."""
    return f"""You are helping with {context}.

Follow these guidelines:
1. Step one
2. Step two
"""
```

### Step 5: Configure

Edit `server/config/settings.yaml`:

```yaml
mcp:
  name: "My MCP Server"
  version: "1.0.0"
  description: "What your MCP does"

# Your custom configuration
your_service:
  api_key: "${YOUR_API_KEY}"  # From .env
  endpoint: "https://api.example.com"
  timeout: 30

database:
  host: "${DB_HOST:localhost}"
  port: "${DB_PORT:5432}"
```

### Step 6: Test

```bash
# Run tests
cd tests
pip install -r requirements.txt
pytest -v

# Test your tool manually
docker-compose up -d
docker-compose logs -f
```

---

## �️ Database Setup (Optional)

### When Do You Need a Database?

Add a database to your MCP if you need:

- ✅ **Caching** - Store API responses, reduce external calls
- ✅ **State Management** - Track sessions, user preferences, workflow state
- ✅ **Data Analysis** - Query and analyze data from external systems
- ✅ **Logging/Audit** - Store operation history, compliance tracking

### Quick Start: Add Database to Your MCP

#### Step 1: Choose Your Database

The template includes a generic connector in `server/db/connector.py`. Choose:

- **PostgreSQL** → Use `asyncpg` (recommended for async MCP)
- **MySQL** → Use `aiomysql`
- **Oracle** → Use `oracledb` (async mode)
- **SQL Server** → Use `aioodbc`
- **SQLite** → Use `aiosqlite` (for simple/local storage)
- **MongoDB** → Use `motor` (async MongoDB driver)

#### Step 2: Add Database Package

Add to `server/requirements.txt`:

```txt
# PostgreSQL
asyncpg==0.29.0

# Or MySQL
# aiomysql==0.2.0

# Or Oracle
# oracledb==2.0.0
```

#### Step 3: Configure Database Connection

Add to `server/config/settings.yaml`:

```yaml
database:
  type: postgresql  # postgresql, mysql, oracle, sqlserver, sqlite
  host: localhost
  port: 5432
  database: mydb
  user: dbuser
  password: ""  # Set DB_PASSWORD in .env
  
  # Connection pool settings
  pool:
    min_size: 2
    max_size: 10
    timeout: 30
```

Add to `.env`:

```bash
# Database credentials
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=dbuser
DB_PASSWORD=your_secure_password
```

#### Step 4: Implement Database Connector

Edit `server/db/connector.py` - example for PostgreSQL:

```python
"""
Database Connector
==================
PostgreSQL connection with async support
"""

import logging
import asyncpg
from config import get_config

logger = logging.getLogger(__name__)

class DatabaseConnector:
    """PostgreSQL connection pool manager"""
    
    def __init__(self):
        self.config = get_config()
        self.pool = None
    
    async def connect(self):
        """Initialize connection pool"""
        try:
            db_config = self.config.get('database', {})
            
            # Get credentials from env vars first
            import os
            host = os.getenv('DB_HOST', db_config.get('host', 'localhost'))
            port = int(os.getenv('DB_PORT', db_config.get('port', 5432)))
            database = os.getenv('DB_NAME', db_config.get('database'))
            user = os.getenv('DB_USER', db_config.get('user'))
            password = os.getenv('DB_PASSWORD', db_config.get('password'))
            
            pool_config = db_config.get('pool', {})
            
            self.pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                min_size=pool_config.get('min_size', 2),
                max_size=pool_config.get('max_size', 10),
                command_timeout=pool_config.get('timeout', 30)
            )
            
            logger.info(f"✅ Database pool created: {database}@{host}")
        except Exception as e:
            logger.error(f"❌ Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    async def execute_query(self, query: str, *params):
        """
        Execute a query and return results
        
        Args:
            query: SQL query with $1, $2, etc. placeholders
            params: Query parameters (prevents SQL injection)
        
        Returns:
            List of rows as dicts
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    async def execute(self, query: str, *params):
        """Execute a query without returning results (INSERT, UPDATE, DELETE)"""
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *params)
        except Exception as e:
            logger.error(f"Execute failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            if not self.pool:
                return False
            
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            return True
        except:
            return False

# Global instance
_db = None

def get_db() -> DatabaseConnector:
    """Get database connector instance"""
    global _db
    if _db is None:
        _db = DatabaseConnector()
    return _db
```

#### Step 5: Initialize Database in Server

Edit `server/server.py` - add database lifecycle:

```python
# At top of file
from db.connector import get_db

# In lifespan function (around line 145)
@contextlib.asynccontextmanager
async def lifespan(app_):
    # Startup
    logger.info("🚀 Starting server...")
    
    # Initialize database
    try:
        db = get_db()
        await db.connect()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization failed: {e}")
        logger.warning("Continuing without database")
    
    # ... existing startup code ...
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    
    # Disconnect database
    try:
        db = get_db()
        await db.disconnect()
    except:
        pass
```

#### Step 6: Use Database in Tools

Example tool using database:

```python
# server/tools/data_tools.py
import asyncio
from mcp_app import mcp
from db.connector import get_db
import logging

logger = logging.getLogger(__name__)

@mcp.tool(
    name="query_data",
    description="Query data from the database. Returns cached results if available."
)
def query_data(table_name: str, limit: int = 100):
    """Query data from database"""
    
    async def _query():
        try:
            db = get_db()
            
            # Use parameterized query to prevent SQL injection
            query = """
                SELECT * FROM {table}
                LIMIT $1
            """.format(table=table_name)  # Table name from string formatting
            
            results = await db.execute_query(query, limit)
            
            return {
                "status": "success",
                "count": len(results),
                "data": results
            }
            
        except Exception as e:
            logger.exception(f"Query failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    # Run async function
    return asyncio.run(_query())
```

#### Step 7: Add Database Health Check

The health check automatically includes database status if you add to `server/server.py`:

```python
@app.get("/health/deep")
async def health_deep():
    """Detailed health check including database"""
    
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # ... existing checks ...
    
    # Database check
    try:
        from db.connector import get_db
        db = get_db()
        db_healthy = await db.health_check()
        health["checks"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "connected": db_healthy
        }
    except Exception as e:
        health["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    return health
```

#### Step 8: Add to Docker Compose (Optional)

If you need a database container for development:

```yaml
# docker-compose.yml
services:
  template_mcp:
    # ... existing config ...
    depends_on:
      - postgres
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=mcpdb
      - DB_USER=mcpuser
      - DB_PASSWORD=${DB_PASSWORD:-changeme}
  
  postgres:
    image: postgres:16
    container_name: mcp_postgres
    environment:
      POSTGRES_DB: mcpdb
      POSTGRES_USER: mcpuser
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcpuser"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Database Patterns & Best Practices

#### Caching Pattern

```python
@mcp.tool(name="get_expensive_data", description="Get data with caching")
def get_expensive_data(resource_id: str):
    async def _fetch():
        db = get_db()
        
        # 1. Check cache
        cached = await db.execute_query(
            "SELECT data, cached_at FROM cache WHERE resource_id = $1 AND cached_at > NOW() - INTERVAL '1 hour'",
            resource_id
        )
        
        if cached:
            return {"status": "success", "data": cached[0]["data"], "source": "cache"}
        
        # 2. Fetch from external API
        data = await fetch_from_external_api(resource_id)
        
        # 3. Cache result
        await db.execute(
            "INSERT INTO cache (resource_id, data, cached_at) VALUES ($1, $2, NOW()) ON CONFLICT (resource_id) DO UPDATE SET data = $2, cached_at = NOW()",
            resource_id, json.dumps(data)
        )
        
        return {"status": "success", "data": data, "source": "api"}
    
    return asyncio.run(_fetch())
```

#### Audit Logging Pattern

```python
@mcp.tool(name="important_operation", description="Operation with audit trail")
def important_operation(action: str, user_id: str):
    async def _execute():
        db = get_db()
        
        try:
            # Log operation start
            await db.execute(
                "INSERT INTO audit_log (user_id, action, status, timestamp) VALUES ($1, $2, $3, NOW())",
                user_id, action, "started"
            )
            
            # Do the operation
            result = perform_operation(action)
            
            # Log success
            await db.execute(
                "UPDATE audit_log SET status = $1, result = $2 WHERE user_id = $3 AND action = $4 AND status = $5",
                "completed", json.dumps(result), user_id, action, "started"
            )
            
            return {"status": "success", "result": result}
            
        except Exception as e:
            # Log failure
            await db.execute(
                "UPDATE audit_log SET status = $1, error = $2 WHERE user_id = $3 AND action = $4 AND status = $5",
                "failed", str(e), user_id, action, "started"
            )
            raise
    
    return asyncio.run(_execute())
```

### Database Migration (Optional)

For managing schema changes, consider using Alembic:

```bash
# Add to requirements.txt
alembic==1.13.0

# Initialize Alembic
alembic init alembic

# Create migration
alembic revision -m "create tables"

# Apply migrations
alembic upgrade head
```

See [Alembic documentation](https://alembic.sqlalchemy.org/) for details.

---

## �📚 Knowledge Base Setup

The knowledge base provides LLM-queryable documentation.

### Why Use It?

- ✅ **Never goes stale** - Documentation updates with code
- ✅ **LLM-accessible** - Built-in help tools for querying
- ✅ **Maintainable** - Just edit markdown files
- ✅ **Version-controlled** - Docs live with code

### Files to Create

1. **`overview.md`** - Copy from `_TEMPLATE_overview.md`
   - What the MCP does
   - When to use it
   - Available tools
   - Security & auth

2. **`workflows.md`** - Step-by-step guides
   - Common task workflows
   - Example conversations
   - Tool combinations

3. **`architecture.md`** - How it works
   - Internal design
   - Data flow diagrams (Mermaid)
   - Configuration impact

4. **`troubleshooting.md`** - Error solutions
   - Common errors
   - Causes and fixes
   - Debugging tips

5. **`tools/tool_name.md`** - Per-tool docs
   - Copy from `_TEMPLATE_tool_doc.md`
   - Parameters, outputs, examples
   - Real-world usage scenarios

### Accessing from LLMs

The `help_tools.py` provides two tools:

```python
# List available documentation
list_knowledge_base_topics()

# Read specific documentation
get_knowledge_base_content(topic="overview")
get_knowledge_base_content(topic="workflows")
get_knowledge_base_content(topic="tool:my_tool_name")
```

---

## 🎯 Feedback System (Optional)

This template includes an **optional** interactive feedback system that allows users to report bugs, request features, and suggest improvements directly through the MCP.

**Status:** ⚠️ Disabled by default - requires configuration to enable

### Features

- ✅ **Interactive Quality Checking** - Analyzes feedback clarity, suggests improvements
- ✅ **Multi-Level Rate Limiting** - Per-user and per-team limits to prevent spam
- ✅ **GitHub Integration** - Automatically creates GitHub issues
- ✅ **Admin Dashboard** - View feedback stats, submissions, and blocks
- ✅ **LLM-Powered Improvement** - Help users rewrite unclear feedback

### Quick Enable

1. **Edit `server/config/settings.yaml`:**
```yaml
feedback:
  enabled: true  # Change from false to true
  github:
    repo: "YOUR_USERNAME/YOUR_REPO"
    maintainer: "YOUR_GITHUB_USERNAME"
```

2. **Set GitHub token in `.env`:**
```bash
GITHUB_TOKEN=github_pat_YOUR_TOKEN_HERE
```

3. **Restart server:**
```bash
docker-compose restart
```

### Documentation

See [FEEDBACK_SETUP_GUIDE.md](FEEDBACK_SETUP_GUIDE.md) for:
- Complete configuration options
- Rate limiting customization
- Admin tools usage
- Quality checking details
- Testing procedures
- Troubleshooting guide

### Available Tools (When Enabled)

**User Tools:**
- `report_mcp_issue_interactive` - Report bugs, features, improvements
- `improve_my_feedback` - Get help improving unclear feedback
- `search_mcp_issues` - Search existing GitHub issues

**Admin Tools (require admin API key):**
- `get_feedback_dashboard` - View complete feedback dashboard
- `get_github_issues_summary` - See GitHub issues created from feedback
- `get_feedback_by_client` - View specific team's feedback

---

## 🌐 Traefik Gateway Integration

This template is ready for Traefik gateway integration (labels are commented out).

### Without Traefik (Default)

Direct port binding - each MCP on its own port:

```yaml
# docker-compose.yml (current state)
services:
  template_mcp:
    ports:
      - "8100:8000"  # Direct port binding
```

Access: `http://localhost:8100/`

### With Traefik (Path-based Routing)

All MCPs through single gateway with path prefixes:

**1. Enable Traefik in `.env`**:
```bash
USE_TRAEFIK=true
MCP_NAME=template-mcp
```

**2. Edit `docker-compose.yml`**:
```yaml
services:
  template_mcp:
    # Comment out ports
    # ports:
    #   - "8100:8000"
    
    networks:
      - mcp_network  # Uncomment this
    
    labels:  # Uncomment all labels
      - "traefik.enable=true"
      - "traefik.http.routers.template-mcp.rule=PathPrefix(`/template-mcp`)"
      # ... etc
```

**3. Start gateway first**:
```bash
cd ../mcp-gateway
docker-compose up -d

cd ../template_mcp
docker-compose up -d
```

Access: `http://localhost:8000/template-mcp/`

### Traefik Benefits

- ✅ **Single entry point** - All MCPs through one gateway
- ✅ **Path-based routing** - `/mcp1`, `/mcp2`, etc.
- ✅ **Load balancing** - Distribute requests
- ✅ **Health checks** - Automatic unhealthy instance removal
- ✅ **TLS termination** - HTTPS at gateway

---

## 💻 Development Guide

### Hot Reload

The server automatically reloads when code changes:

```bash
# Start with hot reload (default)
docker-compose up -d

# Edit a tool
nano server/tools/my_tool.py

# Changes automatically detected and server reloads!
# Check logs to see reload:
docker-compose logs -f
```

### Adding Dependencies

```bash
# Add to requirements.txt
echo "requests==2.31.0" >> server/requirements.txt

# Rebuild container
docker-compose up -d --build
```

### Debugging

```bash
# View logs
docker-compose logs -f

# View specific log levels
docker-compose logs -f | grep ERROR

# Enter container
docker-compose exec template_mcp bash

# Check what's loaded
curl http://localhost:8100/version
```

### Configuration Hierarchy

1. **Default**: `server/config/settings.yaml`
2. **Environment override**: `server/config/settings.{ENV}.yaml`
3. **Environment variables**: `.env` file

Example:
```bash
# Set environment
ENV=prod

# Loads: settings.yaml + settings.prod.yaml
# Then applies .env variables
```

---

## 🧪 Testing

### Unit Tests

```bash
cd tests
pip install -r requirements.txt

# Run all tests
pytest -v

# Run specific test
pytest test_example_tool.py -v

# With coverage
pytest --cov=server --cov-report=html
```

### Integration Tests

```bash
# Start server
docker-compose up -d

# Run integration tests
pytest tests/integration/ -v
```

### Manual Testing

```bash
# Health check
curl http://localhost:8100/healthz

# Deep health
curl http://localhost:8100/health/deep | jq

# List knowledge base
curl http://localhost:8100/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_knowledge_base_topics"}}'
```

---

## 🚀 Deployment

### Docker Deployment

```bash
# Production build
ENV=prod docker-compose up -d --build

# Check status
docker-compose ps

# View prod logs
docker-compose logs -f
```

### Environment-Specific Config

Create `server/config/settings.prod.yaml`:

```yaml
mcp:
  name: "My MCP (Production)"
  
logging:
  level: "WARNING"
  format: "json"
  
rate_limiting:
  enabled: true
  max_requests: 100
  window_seconds: 60
```

### Health Checks

Configure your orchestrator to use:

- **Liveness**: `GET /healthz` - Simple "OK" response
- **Readiness**: `GET /health/deep` - Checks dependencies

Example Kubernetes:
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/deep
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## 🤖 For LLMs

> **When an LLM is helping create a new MCP using this template:**

### Critical Files to Read

1. **[SPEC.md](SPEC.md)** - Complete technical specification
   - Mandatory patterns
   - Critical rules (especially Rule #0)
   - File structure requirements
   - Best practices

2. **[server/server.py](server/server.py)** - BASE TEMPLATE
   - Hot reload setup
   - Auto-discovery
   - Middleware configuration
   - 💡 Modify if you need custom middleware or startup logic

3. **[server/mcp_app.py](server/mcp_app.py)** - BASE TEMPLATE
   - FastMCP initialization
   - Keep minimal by default
   - 💡 Modify if you need custom MCP configuration

4. **[server/config.py](server/config.py)** - BASE TEMPLATE
   - Configuration loading
   - Environment handling
   - 💡 Modify if you need custom config parsing

### What to Customize

✅ **ALWAYS CUSTOMIZE**:
- `server/config/settings.yaml` - User's configuration
- `server/tools/*.py` - User's tools (follow SPEC.md Rule #0!)
- `server/knowledge_base/*.md` - Documentation
- `README.md` - Update this file with user's MCP details
- `.env` - User's environment variables

⭐ **USE AS BASE (modify if needed)**:
- `server/server.py` - Core infrastructure (works well as-is, but can customize middleware/startup)
- `server/mcp_app.py` - FastMCP setup (minimal by default, extend if needed)
- `server/config.py` - Config loader (handles YAML/env, extend for custom parsing)
- `server/utils/*.py` - Utility functions (extend with your own helpers)

### Knowledge Base Setup

Always create these files by copying templates:

```bash
# Overview
cp server/knowledge_base/_TEMPLATE_overview.md server/knowledge_base/overview.md

# Tool documentation (for each tool)
cp server/knowledge_base/_TEMPLATE_tool_doc.md server/knowledge_base/tools/user_tool.md
```

### Traefik Integration

Ask user: "Will this MCP use a Traefik gateway?"

- **YES**: Uncomment labels in `docker-compose.yml`, set `USE_TRAEFIK=true` in `.env`
- **NO**: Leave as-is (direct port binding)

### Tool Pattern (CRITICAL)

**ALWAYS use this pattern** (see SPEC.md Rule #0):

```python
@mcp.tool(
    name="tool_name",  # ✅ REQUIRED - explicit name
    description="..."  # ✅ REQUIRED - clear description
)
def tool_name(param: str):  # ✅ NOT async
    """Docstring."""
    return result  # ✅ Direct return
```

**NEVER use**:
```python
@mcp.tool()  # ❌ Empty decorator
async def tool_name():  # ❌ Async
    return {"result": ...}  # ❌ With type annotation
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/template_mcp/issues)
- **Spec**: See [SPEC.md](SPEC.md) for detailed patterns
- **Examples**: Check `server/tools/example_tool.py` for working examples

---

## ✅ Checklist: Creating Your MCP

- [ ] Clone template and remove `.git` folder
- [ ] Update `.env` with your MCP name and port
- [ ] Customize `server/config/settings.yaml`
- [ ] Create knowledge base documentation (copy from templates)
- [ ] Add your tools to `server/tools/`
- [ ] Document each tool in `knowledge_base/tools/`
- [ ] Add resources/prompts if needed
- [ ] Update this README with your MCP details
- [ ] Decide on Traefik (yes/no) and configure accordingly
- [ ] Write tests in `tests/`
- [ ] Test locally: `docker-compose up -d`
- [ ] Verify health: `curl http://localhost:PORT/healthz`
- [ ] Update LICENSE with your information
- [ ] Initialize new git repo and push

---

**Template Version**: 2.0  
**Last Updated**: January 6, 2026  
**FastMCP Version**: 2.x
