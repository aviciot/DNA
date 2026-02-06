"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))
