# MCP Requirements Specification Template

> **Purpose**: This template defines the requirements for a new MCP server. Fill out all sections with your specific requirements, and LLMs will use this along with the template structure and rules to generate a complete, working MCP.

---

## 📋 MCP Identity

**Project Name**: [Your MCP Name - e.g., "Salesforce MCP", "Jira MCP", "Database Analytics MCP"]

**Short Name**: [kebab-case name - e.g., "salesforce-mcp", "jira-mcp", "db-analytics-mcp"]

**Version**: [e.g., "1.0.0"]

**Description**: [One paragraph describing what this MCP does and why it's useful]

**Target Users**: [Who will use this? e.g., "Developers", "Data Analysts", "DevOps Engineers"]

---

## 🎯 Core Purpose & Capabilities

### What Problem Does It Solve?

[Describe the problem this MCP addresses]

### Key Capabilities

List the main things this MCP can do:

1. **[Capability 1]**: [Description]
2. **[Capability 2]**: [Description]
3. **[Capability 3]**: [Description]

### Example Use Cases

1. **Use Case 1**: [Describe a specific scenario where this MCP would be used]
2. **Use Case 2**: [Another scenario]
3. **Use Case 3**: [Another scenario]

---

## 🔌 External Systems & Integrations

### Required External Systems

List all external systems this MCP needs to connect to:

#### System 1: [e.g., "Salesforce API"]

- **Type**: [API, Database, File System, etc.]
- **Connection Method**: [REST API, JDBC, File Path, etc.]
- **Authentication**: [OAuth2, API Key, Username/Password, etc.]
- **Required Credentials**:
  - `[ENV_VAR_1]`: [Description - e.g., "Salesforce Client ID"]
  - `[ENV_VAR_2]`: [Description - e.g., "Salesforce Client Secret"]
- **Base URL/Endpoint**: [e.g., "https://api.salesforce.com/v1"]
- **Documentation**: [Link to API docs if available]

#### System 2: [e.g., "PostgreSQL Database"]

- **Type**: [Database type]
- **Connection Method**: [e.g., "asyncpg", "psycopg2"]
- **Authentication**: [Username/Password]
- **Required Credentials**:
  - `DB_HOST`: Database host
  - `DB_PORT`: Database port
  - `DB_NAME`: Database name
  - `DB_USER`: Database username
  - `DB_PASSWORD`: Database password
- **Connection Pooling**: [Yes/No - if yes, specify min/max connections]
- **Schema/Tables**: [List key tables or schemas this MCP will access]

---

## 🛠️ Tools (MCP Functions)

List all tools this MCP should provide. Follow Rule #0 patterns!

### Tool 1: [tool_name]

**Name**: `[exact_function_name]`

**Description**: [Clear description of what this tool does and when to use it]

**Parameters**:
- `param1` (string, required): [Description]
- `param2` (integer, optional, default=10): [Description]
- `param3` (boolean, optional, default=false): [Description]

**Returns**: [Describe return format - e.g., "Dictionary with 'status', 'data', 'message' fields"]

**Example Input**:
```json
{
  "param1": "example_value",
  "param2": 20
}
```

**Example Output**:
```json
{
  "status": "success",
  "data": {
    "result": "example result"
  },
  "message": "Operation completed"
}
```

**Error Handling**: [List possible errors and how they're handled]

**Special Notes**: [Any important implementation details]

---

### Tool 2: [another_tool_name]

[Repeat the same structure for each tool]

---

## 📦 Resources (Static Content)

List any MCP resources this server should provide.

### Resource 1: [resource_name]

**URI**: `scheme://resource_name` (e.g., `salesforce://schema`, `jira://project_template`)

**Description**: [What this resource provides]

**Content Type**: [JSON, Markdown, XML, etc.]

**Content**: [Describe or provide example of the content]

---

## 💬 Prompts (LLM Guidance)

List any prompts this MCP should provide to guide LLMs.

### Prompt 1: [prompt_name]

**Name**: `[prompt_name]`

**Description**: [What guidance this prompt provides]

**Context Parameters**: 
- `context` (optional): [Description of context variations]

**Prompt Template**: [Describe the prompt structure or provide template]

---

## ⚙️ Configuration Requirements

### Environment Variables

List all environment variables this MCP needs:

```bash
# System Connection
[ENV_VAR_1]=[Description]
[ENV_VAR_2]=[Description]

# Authentication
AUTH_ENABLED=[true/false - whether to enable authentication]
AUTH_TOKEN=[API token if authentication enabled]

# MCP Configuration
MCP_CONTAINER_NAME=[Docker container name]
MCP_NAME=[MCP service name]
MCP_PORT=[External port, e.g., 8200]

# Optional Features
[FEATURE_ENABLED]=[true/false]
```

### Configuration File (settings.yaml)

Describe custom configuration sections needed:

```yaml
# Your custom sections
your_system:
  endpoint: "https://api.example.com"
  timeout: 30
  retry_attempts: 3

database:  # If database is needed
  host: "localhost"
  port: 5432
  pool_size: 10
  
cache:  # If caching is needed
  enabled: true
  ttl: 3600
```

---

## 🗄️ Database Requirements (if applicable)

### Does This MCP Need a Database?

- [ ] **No** - Skip this section
- [ ] **Yes** - Complete sections below

### Database Type

- [ ] PostgreSQL
- [ ] MySQL
- [ ] Oracle
- [ ] SQL Server
- [ ] MongoDB
- [ ] SQLite
- [ ] Other: [Specify]

### Database Purpose

- [ ] **Caching** - Store cached results from external APIs
- [ ] **State Management** - Track MCP state, user sessions
- [ ] **Data Storage** - Primary data storage
- [ ] **Query Target** - MCP queries this database for data
- [ ] **Logging/Audit** - Store operation logs

### Database Schema

If database is needed, describe tables/collections:

#### Table 1: [table_name]

```sql
CREATE TABLE table_name (
    id SERIAL PRIMARY KEY,
    field1 VARCHAR(255) NOT NULL,
    field2 INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Purpose**: [Why this table exists]

#### Table 2: [another_table]

[Repeat for each table]

### Connection Requirements

- **Connection Pool Size**: [e.g., min=2, max=10]
- **Connection Timeout**: [e.g., 30 seconds]
- **Retry Logic**: [Yes/No - describe if yes]
- **Health Check Query**: [e.g., "SELECT 1"]

---

## 📚 Knowledge Base Documentation

What documentation should be in the knowledge base?

### Overview (overview.md)

[Describe what should be in the overview - purpose, capabilities, when to use]

### Workflows (workflows.md)

List step-by-step workflows to document:

1. **Workflow 1**: [e.g., "How to query Salesforce accounts"]
   - Step 1: [...]
   - Step 2: [...]

2. **Workflow 2**: [Another common workflow]

### Architecture (architecture.md)

[Describe system architecture, data flow, how components interact]

**Should Include Diagrams**: [Yes/No]

### Troubleshooting (troubleshooting.md)

List common errors to document:

1. **Error 1**: [e.g., "Connection timeout"]
   - **Cause**: [Why it happens]
   - **Solution**: [How to fix]

2. **Error 2**: [Another common error]

---

## 🔒 Security Requirements

### Authentication Method

- [ ] **None** - Public MCP, no auth needed
- [ ] **Bearer Token** - Simple API token
- [ ] **OAuth2** - OAuth2 flow with external provider
- [ ] **Basic Auth** - Username/password
- [ ] **API Key** - API key in header
- [ ] **Custom** - Describe: [...]

### Authorization

- [ ] **Not needed** - All users have same access
- [ ] **Role-based** - Different roles have different permissions
  - Roles: [e.g., "admin", "user", "readonly"]
- [ ] **Resource-based** - Permissions per resource
- [ ] **Custom** - Describe: [...]

### Sensitive Data Handling

List any sensitive data this MCP handles:

1. **[Data Type 1]**: [e.g., "User passwords"] - **Handling**: [e.g., "Never log, always hash"]
2. **[Data Type 2]**: [e.g., "API keys"] - **Handling**: [e.g., "Mask in logs"]

### Rate Limiting

- [ ] **Not needed**
- [ ] **Required** - Specify limits:
  - Requests per minute: [e.g., 60]
  - Requests per hour: [e.g., 1000]
  - Per-user or global: [specify]

---

## 🎨 Special Features & Requirements

### Caching Strategy

- [ ] **No caching needed**
- [ ] **In-memory caching** (cache expires on restart)
- [ ] **Persistent caching** (database or Redis)

If caching is needed:
- **What to cache**: [e.g., "API responses", "Database query results"]
- **Cache TTL**: [e.g., "1 hour for API responses, 24 hours for metadata"]
- **Cache invalidation**: [e.g., "On demand via admin tool", "Time-based only"]

### Background Tasks

Does this MCP need background tasks (schedulers, workers)?

- [ ] **No background tasks**
- [ ] **Yes** - Describe:

#### Task 1: [task_name]

- **Frequency**: [e.g., "Every 5 minutes", "Daily at midnight"]
- **Purpose**: [What it does]
- **Implementation**: [Cron, Celery, simple scheduler, etc.]

### Webhook Support

- [ ] **No webhooks**
- [ ] **Incoming webhooks** - This MCP receives webhooks
  - From: [System that sends webhooks]
  - Endpoints: [List webhook endpoints needed]
- [ ] **Outgoing webhooks** - This MCP sends webhooks
  - To: [System that receives webhooks]
  - Events: [What triggers webhooks]

### Real-time Features

- [ ] **No real-time features**
- [ ] **WebSocket support** - Live updates
- [ ] **Server-Sent Events (SSE)** - Push notifications
- [ ] **Polling** - Regular status checks

Describe requirements: [...]

---

## 📊 Performance Requirements

### Expected Load

- **Requests per second**: [e.g., "10-50 under normal load"]
- **Concurrent users**: [e.g., "5-10 simultaneous users"]
- **Data volume**: [e.g., "Processing 1000-10000 records per query"]

### Response Time Requirements

- **Fast operations** (< 1 second): [e.g., "List queries", "Cache lookups"]
- **Medium operations** (1-5 seconds): [e.g., "Database queries", "API calls"]
- **Slow operations** (5-30 seconds): [e.g., "Large data exports", "Complex analysis"]
- **Long-running operations** (> 30 seconds): [e.g., "Batch processing"] - Should be async

### Scalability

- [ ] **Single instance** - No scaling needed
- [ ] **Horizontal scaling** - Multiple instances behind load balancer
- [ ] **Vertical scaling** - Needs more CPU/memory

---

## 🧪 Testing Requirements

### Test Coverage

What needs to be tested?

- [ ] **Unit tests** for all tools
- [ ] **Integration tests** with external systems (mocked)
- [ ] **End-to-end tests** with real systems (optional)
- [ ] **Performance tests**
- [ ] **Security tests**

### Test Data

- [ ] **Use fake/mock data**
- [ ] **Use test/staging environment**
- [ ] **Requires special test setup**: [Describe]

---

## 📦 Dependencies

### Python Packages (beyond template defaults)

List additional Python packages needed:

```txt
# Required packages
package-name==version  # Purpose: [why needed]
another-package>=2.0   # Purpose: [why needed]

# Optional packages
optional-package==1.0  # Purpose: [why needed] (Optional)
```

### External Services

List any external services this MCP depends on:

1. **[Service Name]**: [e.g., "Redis"] - **Purpose**: [e.g., "Caching layer"]
   - **Required**: [Yes/No]
   - **Setup**: [How to set up locally/production]

2. **[Another Service]**: [...]

---

## 🚀 Deployment Requirements

### Docker

- [ ] **Single container** - Just the MCP
- [ ] **Docker Compose** - MCP + dependencies (database, Redis, etc.)
- [ ] **Special requirements**: [Describe]

### Network Requirements

- [ ] **Outbound internet access** - Needs to call external APIs
- [ ] **Database access** - Needs to connect to database
- [ ] **No special requirements**

### Health Checks

What should health checks verify?

- [ ] **Server is running** (basic `/healthz`)
- [ ] **External API connectivity**
- [ ] **Database connectivity**
- [ ] **Cache availability**
- [ ] **Custom checks**: [Describe]

---

## 📝 Development Notes

### Special Considerations

[Any special notes for the LLM developer - edge cases, known issues, specific requirements]

### Implementation Priority

Which tools/features should be implemented first?

1. **High Priority** (MVP - Must have):
   - [Tool/Feature 1]
   - [Tool/Feature 2]

2. **Medium Priority** (Nice to have):
   - [Tool/Feature 3]

3. **Low Priority** (Future enhancements):
   - [Tool/Feature 4]

### Known Limitations

[List any known limitations or constraints]

---

## ✅ Success Criteria

How do we know this MCP is working correctly?

1. [ ] All required tools are implemented and tested
2. [ ] Can successfully connect to [external system 1]
3. [ ] Can successfully connect to [external system 2]
4. [ ] Health checks pass
5. [ ] Documentation is complete
6. [ ] [Custom criteria 1]
7. [ ] [Custom criteria 2]

---

## 📖 Example: Complete MCP Requirement

Below is a filled-out example for reference:

<details>
<summary>Click to expand: GitHub MCP Requirements Example</summary>

### MCP Identity

**Project Name**: GitHub Repository Manager MCP
**Short Name**: github-mcp
**Version**: 1.0.0
**Description**: MCP server for managing GitHub repositories, issues, and pull requests through natural language interactions
**Target Users**: Developers, Project Managers

### Core Purpose & Capabilities

**What Problem Does It Solve?**
Developers spend time switching between IDE and GitHub UI for repository management. This MCP allows managing GitHub directly from AI assistants.

**Key Capabilities**:
1. **Repository Management**: Create, list, search repositories
2. **Issue Tracking**: Create, update, search, comment on issues
3. **Pull Request Management**: Create PRs, review, merge, get status

### External Systems & Integrations

#### System 1: GitHub REST API
- **Type**: REST API
- **Connection Method**: HTTPS REST API
- **Authentication**: Personal Access Token (PAT)
- **Required Credentials**:
  - `GITHUB_TOKEN`: GitHub Personal Access Token with repo scope
  - `GITHUB_ORG`: Organization name (optional)
- **Base URL**: https://api.github.com
- **Documentation**: https://docs.github.com/en/rest

### Tools

#### Tool 1: list_repositories

**Name**: `list_repositories`

**Description**: List repositories for authenticated user or organization. Use when user asks to "show repos" or "list my repositories".

**Parameters**:
- `org` (string, optional): Organization name. If not provided, lists user's repos
- `type` (string, optional, default="all"): Filter by type (all, owner, member)
- `limit` (integer, optional, default=30): Max repos to return

**Returns**: Dictionary with 'repositories' list and 'count'

**Example Input**:
```json
{
  "org": "my-company",
  "type": "owner",
  "limit": 10
}
```

[...continue with more tools...]

### Database Requirements

**Does This MCP Need a Database?**: No - Stateless, all data from GitHub API

### Configuration

```yaml
github:
  api_url: "https://api.github.com"
  timeout: 30
  default_org: ""  # Optional default organization
```

</details>

---

## 🎯 Instructions for LLMs

When an LLM receives this requirements document:

1. **Read the entire document** carefully
2. **Refer to** `.amazonq/rules/mcp.md` for development rules
3. **Use** `SPEC.md` for technical patterns
4. **Follow Rule #0** (tool decorators) religiously
5. **Implement** all required tools, resources, prompts
6. **Set up** database if specified
7. **Create** knowledge base documentation
8. **Add** health checks for external systems
9. **Test** that all requirements are met
10. **Document** any deviations or additional features

**Priority Order**:
1. Core tools (High Priority items)
2. External system connections
3. Database setup (if needed)
4. Resources and prompts
5. Knowledge base documentation
6. Medium/Low priority features

**Quality Checklist**:
- [ ] All tools follow Rule #0 patterns
- [ ] Error handling is comprehensive
- [ ] External connections have retry logic
- [ ] Sensitive data is never logged
- [ ] Configuration follows 3-layer pattern
- [ ] Documentation is complete
- [ ] Tests cover critical paths

---

**Now fill out this template with YOUR MCP requirements!** 🚀
