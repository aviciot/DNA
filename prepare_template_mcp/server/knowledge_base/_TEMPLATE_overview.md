# [Your MCP Name] - Overview

> **Instructions**: Copy this template to `overview.md` and customize all sections marked with [CUSTOMIZE]

## 🎯 What Does This MCP Do?

[CUSTOMIZE: Brief 2-3 sentence description of your MCP's purpose]

This MCP provides [MAIN CAPABILITY] for [TARGET SYSTEM/SERVICE]. It enables [KEY BENEFIT] without [LIMITATION YOU SOLVE].

**Example**: "This MCP provides comprehensive query analysis for Oracle and MySQL databases. It enables performance optimization and troubleshooting without executing queries, making it safe for production use."

## 🌟 Key Capabilities

[CUSTOMIZE: List 4-6 main capabilities]

1. **[Capability 1]** - [Brief description]
2. **[Capability 2]** - [Brief description]
3. **[Capability 3]** - [Brief description]
4. **[Capability 4]** - [Brief description]

## 🚀 When to Use This MCP

### ✅ Use this MCP when:
[CUSTOMIZE: List 4-6 scenarios where this MCP is the right choice]

- User needs to [SCENARIO 1]
- Application requires [SCENARIO 2]
- You want to [SCENARIO 3]
- Team is working on [SCENARIO 4]

### ❌ Don't use this MCP when:
[CUSTOMIZE: List 2-3 scenarios where this MCP is NOT appropriate]

- You need to [OUT OF SCOPE 1]
- The use case requires [OUT OF SCOPE 2]
- Your system doesn't [REQUIREMENT NOT MET]

## 🔧 Available Tools

[CUSTOMIZE: List your main tools with brief descriptions]

### Primary Tools

| Tool Name | Purpose | When to Use |
|-----------|---------|-------------|
| `your_main_tool` | [Description] | [Use case] |
| `your_second_tool` | [Description] | [Use case] |
| `your_third_tool` | [Description] | [Use case] |

### Supporting Tools

| Tool Name | Purpose | When to Use |
|-----------|---------|-------------|
| `helper_tool_1` | [Description] | [Use case] |
| `helper_tool_2` | [Description] | [Use case] |

**For detailed tool documentation**, see individual files in [tools/](tools/) folder.

## 📊 Typical Workflow

[CUSTOMIZE: Describe the most common workflow using your MCP]

```
1. User provides [INPUT]
2. LLM calls your_main_tool(param1='...', param2='...')
3. Review returned data for [KEY INFORMATION]
4. Use helper_tool() if needed to [FOLLOW-UP ACTION]
5. Present findings and recommendations to user
```

## 🔐 Security & Access

[CUSTOMIZE: Describe security model, authentication, permissions]

### Authentication
- [AUTH METHOD]: Required/Optional
- [CREDENTIALS]: How to configure

### Required Permissions
[CUSTOMIZE: List permissions or grants needed]

```sql
-- Example for database MCPs
GRANT SELECT ON system_tables TO mcp_user;
GRANT EXECUTE ON dbms_packages TO mcp_user;
```

## ⚙️ Configuration

[CUSTOMIZE: Key configuration settings]

### Required Settings
```yaml
# In server/config/settings.yaml
your_setting:
  api_key: "YOUR_API_KEY"
  endpoint: "https://api.example.com"
  timeout: 30
```

### Environment Variables
```bash
# In .env file
YOUR_MCP_API_KEY=your_key_here
YOUR_MCP_ENDPOINT=https://api.example.com
```

## 📈 Performance Characteristics

[CUSTOMIZE: Performance notes]

- **Response Time**: Typical [X-Y seconds] for [OPERATION]
- **Rate Limits**: [LIMITS IF ANY]
- **Caching**: [CACHING STRATEGY]
- **Token Usage**: [TYPICAL TOKEN RANGE]

## 🔗 External Dependencies

[CUSTOMIZE: List external systems/APIs/databases this MCP connects to]

- **[System 1]**: [Purpose] - [Connection type]
- **[System 2]**: [Purpose] - [Connection type]

## 📚 Related Documentation

- [Workflows Guide](workflows.md) - Step-by-step task guides
- [Architecture](architecture.md) - Internal workings
- [Troubleshooting](troubleshooting.md) - Error solutions
- [Tool: your_main_tool](tools/your_main_tool.md) - Detailed tool reference

## 🆘 Quick Help

**Most commonly used tool**: `your_main_tool`

**Quick example**:
```python
# Most frequent use case
your_main_tool(
    param1="example_value",
    param2="another_value"
)
```

**For more help**: Call `get_knowledge_base_content(topic='workflows')` for step-by-step guides.
