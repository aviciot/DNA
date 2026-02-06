"""
Import utilities for auto-discovery
===================================
Automatically imports all modules in tools/resources/prompts
"""

import pkgutil
import importlib
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def import_submodules(package_name: str):
    """
    Import all submodules in a package
    
    Args:
        package_name: Name of package to import (e.g., 'tools', 'resources', 'prompts')
    """
    try:
        # Get the package path
        package_path = Path(__file__).parent.parent / package_name
        
        if not package_path.exists():
            logger.warning(f"Package path does not exist: {package_path}")
            return
        
        # Import all Python files in the package
        for item in package_path.iterdir():
            if item.is_file() and item.suffix == '.py' and item.stem != '__init__':
                module_name = f"{package_name}.{item.stem}"
                try:
                    importlib.import_module(module_name)
                    logger.info(f"Imported: {module_name}")
                except Exception as e:
                    logger.error(f"Failed to import {module_name}: {e}")
        
    except Exception as e:
        logger.error(f"Error importing submodules from {package_name}: {e}")
