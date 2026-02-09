"""
DNA AI Agents
=============

AI agents for document processing and review.

Available agents:
- BaseAgent: Abstract base class for all agents (provides LLM, telemetry, etc.)
- TemplateAgent: Parse and edit Word document templates
- ReviewerAgent: Review template quality and compliance (TODO: Milestone 2.3)
- WriterAgent: Generate and modify document content (TODO: Future)
"""

from .base_agent import BaseAgent
from .template import TemplateAgent

__all__ = [
    'BaseAgent',
    'TemplateAgent'
]
