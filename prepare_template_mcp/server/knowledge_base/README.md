# Knowledge Base - [Your MCP Name]

This folder contains documentation that LLMs can query to understand how to use this MCP server.

## 📚 Documentation Structure

### Core Documentation
- **[overview.md](overview.md)** - What this MCP does, capabilities, when to use it
- **[workflows.md](workflows.md)** - Step-by-step guides for common tasks
- **[architecture.md](architecture.md)** - How the MCP works internally
- **[troubleshooting.md](troubleshooting.md)** - Common errors and solutions

### Tool Documentation
- **[tools/](tools/)** - Individual tool documentation files
  - Each tool gets its own `.md` file with examples
  - Format: `tool_name.md`

## 🔧 How to Use

### For LLMs
Query the knowledge base using the help tools:
```python
# List available documentation
list_knowledge_base_topics()

# Get specific documentation
get_knowledge_base_content(topic="overview")
get_knowledge_base_content(topic="workflows")
get_knowledge_base_content(topic="tool:your_tool_name")
```

### For Developers
When adding new features:
1. Document new tools in `tools/tool_name.md`
2. Update `workflows.md` if the tool enables new workflows
3. Add troubleshooting entries for common issues
4. Update `overview.md` if capabilities change

## 📝 Template Files

Use the templates in this folder to create consistent documentation:
- `_TEMPLATE_overview.md` - Copy and customize for your MCP
- `_TEMPLATE_tool_doc.md` - Copy for each tool you create

## ✨ Benefits

- **Never goes stale**: Help tools read these files at runtime
- **Easy to maintain**: Just edit markdown files
- **LLM-friendly**: Structured for LLM understanding
- **Version controlled**: Documentation lives with code
