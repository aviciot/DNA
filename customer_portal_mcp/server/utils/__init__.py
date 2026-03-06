"""Import utilities for auto-discovery"""
import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def import_submodules(package_name: str):
    package_path = Path(__file__).parent.parent / package_name
    if not package_path.exists():
        logger.warning(f"Package path does not exist: {package_path}")
        return
    for item in package_path.iterdir():
        if item.is_file() and item.suffix == '.py' and item.stem != '__init__':
            module_name = f"{package_name}.{item.stem}"
            try:
                importlib.import_module(module_name)
                logger.info(f"Imported: {module_name}")
            except Exception as e:
                logger.error(f"Failed to import {module_name}: {e}")
