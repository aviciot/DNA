"""
Tests for example_tool
======================
Demonstrates how to test MCP tools
"""

import pytest
import sys
from pathlib import Path

# Add server to path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))

# Import after path setup
from tools.example_tool import echo


class TestEchoTool:
    """Test cases for echo tool"""
    
    @pytest.mark.asyncio
    async def test_echo_simple(self):
        """Test basic echo functionality"""
        result = await echo("Hello World")
        assert result == "Hello World"
    
    @pytest.mark.asyncio
    async def test_echo_repeat(self):
        """Test echo with repeat"""
        result = await echo("Test", repeat=3)
        assert result == "Test\nTest\nTest"
    
    @pytest.mark.asyncio
    async def test_echo_empty_message(self):
        """Test validation: empty message"""
        result = await echo("")
        assert "Error" in result
        assert "empty" in result.lower()
    
    @pytest.mark.asyncio
    async def test_echo_invalid_repeat(self):
        """Test validation: invalid repeat type"""
        result = await echo("Test", repeat="invalid")
        assert "Error" in result
        assert "integer" in result.lower()
    
    @pytest.mark.asyncio
    async def test_echo_repeat_too_low(self):
        """Test validation: repeat < 1"""
        result = await echo("Test", repeat=0)
        assert "Error" in result
        assert "at least 1" in result
    
    @pytest.mark.asyncio
    async def test_echo_repeat_too_high(self):
        """Test validation: repeat > 10"""
        result = await echo("Test", repeat=15)
        assert "Error" in result
        assert "cannot exceed 10" in result
    
    @pytest.mark.asyncio
    async def test_echo_boundary_repeat(self):
        """Test boundary: repeat = 10 (max allowed)"""
        result = await echo("X", repeat=10)
        lines = result.split("\n")
        assert len(lines) == 10
        assert all(line == "X" for line in lines)


# Run tests:
# cd template_mcp
# pip install pytest pytest-asyncio
# pytest tests/ -v
