# server/tools/help_tools.py
"""
Knowledge Base Help Tools
Provides LLMs with access to MCP documentation
"""

from pathlib import Path
from mcp_app import mcp


# Get path to knowledge_base directory
KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"


def read_knowledge_file(filename: str) -> str:
    """Read markdown file from knowledge_base directory"""
    filepath = KNOWLEDGE_BASE_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding='utf-8')
    return f"❌ File not found: {filename}"


@mcp.tool(
    name="list_knowledge_base_topics",
    description=(
        "📚 List all available documentation topics in the knowledge base.\n\n"
        "Returns a directory of all documentation files including:\n"
        "• Core documentation (overview, workflows, architecture, troubleshooting)\n"
        "• Individual tool documentation\n\n"
        "**Use this when:** User asks 'what help is available?' or 'what can I learn about this MCP?'"
    ),
)
def list_knowledge_base_topics():
    """
    List all available knowledge base topics
    
    Returns:
        Dictionary with categorized list of available documentation
    """
    
    # Scan for available files
    core_docs = []
    tool_docs = []
    
    if KNOWLEDGE_BASE_DIR.exists():
        # Core documentation files
        for doc in ['overview.md', 'workflows.md', 'architecture.md', 'troubleshooting.md']:
            if (KNOWLEDGE_BASE_DIR / doc).exists():
                core_docs.append(doc.replace('.md', ''))
        
        # Tool documentation
        tools_dir = KNOWLEDGE_BASE_DIR / 'tools'
        if tools_dir.exists():
            for tool_file in tools_dir.glob('*.md'):
                if not tool_file.name.startswith('_'):
                    tool_docs.append(f"tool:{tool_file.stem}")
    
    return {
        "available_topics": {
            "core_documentation": core_docs,
            "tool_documentation": tool_docs
        },
        "usage": "Call get_knowledge_base_content(topic='...') to read specific documentation",
        "examples": [
            "get_knowledge_base_content(topic='overview')",
            "get_knowledge_base_content(topic='workflows')",
            f"get_knowledge_base_content(topic='tool:{tool_docs[0].replace('tool:', '')}')" if tool_docs else ""
        ],
        "total_documents": len(core_docs) + len(tool_docs)
    }


@mcp.tool(
    name="get_knowledge_base_content",
    description=(
        "📖 Get documentation from the MCP knowledge base.\n\n"
        "Access comprehensive documentation including:\n"
        "• `overview` - What this MCP does, capabilities, when to use\n"
        "• `workflows` - Step-by-step guides for common tasks\n"
        "• `architecture` - How the MCP works internally (may include diagrams)\n"
        "• `troubleshooting` - Common errors and solutions\n"
        "• `tool:tool_name` - Detailed documentation for specific tools\n\n"
        "**Use this when:** User asks how to use the MCP, needs examples, or wants to understand capabilities"
    ),
)
def get_knowledge_base_content(topic: str = "overview"):
    """
    Get documentation content from knowledge base
    
    Args:
        topic: Documentation topic to retrieve:
            - 'overview', 'workflows', 'architecture', 'troubleshooting'
            - 'tool:tool_name' for specific tool docs
            - Smart keywords: 'help', 'start', 'guide'
    
    Returns:
        String containing the requested markdown documentation
    """
    
    topic_lower = topic.lower().strip()
    
    # Topic mapping with aliases
    topic_map = {
        # Core documentation
        "overview": "overview.md",
        "about": "overview.md",
        "intro": "overview.md",
        "introduction": "overview.md",
        "start": "overview.md",
        "help": "overview.md",
        
        "workflows": "workflows.md",
        "workflow": "workflows.md",
        "guide": "workflows.md",
        "guides": "workflows.md",
        "howto": "workflows.md",
        "how-to": "workflows.md",
        "steps": "workflows.md",
        
        "architecture": "architecture.md",
        "arch": "architecture.md",
        "design": "architecture.md",
        "internals": "architecture.md",
        "how it works": "architecture.md",
        "diagram": "architecture.md",
        "diagrams": "architecture.md",
        
        "troubleshooting": "troubleshooting.md",
        "troubleshoot": "troubleshooting.md",
        "errors": "troubleshooting.md",
        "error": "troubleshooting.md",
        "problems": "troubleshooting.md",
        "issues": "troubleshooting.md",
        "debug": "troubleshooting.md",
        "debugging": "troubleshooting.md",
    }
    
    # Handle tool-specific queries (format: "tool:tool_name")
    if topic_lower.startswith("tool:"):
        tool_name = topic_lower.replace("tool:", "").strip()
        filename = f"tools/{tool_name}.md"
        content = read_knowledge_file(filename)
        
        if "File not found" in content:
            # List available tool docs
            tools_dir = KNOWLEDGE_BASE_DIR / 'tools'
            available = []
            if tools_dir.exists():
                available = [f.stem for f in tools_dir.glob('*.md') if not f.name.startswith('_')]
            
            return f"""❌ Tool documentation not found: {tool_name}

Available tool documentation:
{chr(10).join('• ' + t for t in available) if available else '• No tool documentation available yet'}

To add documentation for this tool:
1. Copy server/knowledge_base/_TEMPLATE_tool_doc.md to server/knowledge_base/tools/{tool_name}.md
2. Customize the template with tool details
3. Restart the MCP server
"""
        
        return content
    
    # Map topic to filename
    filename = topic_map.get(topic_lower)
    
    if not filename:
        # Unknown topic - provide help
        return f"""❌ Unknown topic: {topic}

Available topics:
• overview - What this MCP does
• workflows - Step-by-step guides
• architecture - How it works internally
• troubleshooting - Error solutions
• tool:tool_name - Specific tool documentation

Usage: get_knowledge_base_content(topic='overview')

Or call list_knowledge_base_topics() to see all available documentation.
"""
    
    # Read the file
    content = read_knowledge_file(filename)
    
    # If file doesn't exist, provide setup instructions
    if "File not found" in content:
        return f"""⚠️ Documentation not yet created: {filename}

To set up the knowledge base:
1. Copy templates from server/knowledge_base/_TEMPLATE_*.md
2. Customize for your MCP:
   - _TEMPLATE_overview.md → overview.md
   - _TEMPLATE_tool_doc.md → tools/your_tool.md
3. Fill in all [CUSTOMIZE] sections
4. Remove template markers

See server/knowledge_base/README.md for complete setup instructions.
"""
    
    return content
