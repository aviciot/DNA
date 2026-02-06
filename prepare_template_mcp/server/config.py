"""
Template MCP Configuration Loader
=================================
Loads configuration from settings.yaml with environment variable substitution
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration manager for MCP server"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration
        
        Args:
            config_path: Path to settings.yaml file. If None, uses default location.
        """
        if config_path is None:
            # Check for environment-specific config
            env = os.getenv('ENV', 'default')
            if env == 'dev':
                config_file = 'settings.dev.yaml'
            elif env == 'prod':
                config_file = 'settings.prod.yaml'
            else:
                config_file = 'settings.yaml'
            
            # Default path: server/config/settings.yaml (or env-specific)
            config_path = Path(__file__).parent / "config" / config_file
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._substitute_env_vars()
        logger.info(f"Configuration loaded from {self.config_path}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
    
    def _substitute_env_vars(self):
        """Substitute ${VAR_NAME} with environment variable values"""
        def substitute(obj):
            if isinstance(obj, dict):
                return {k: substitute(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                value = os.getenv(var_name)
                if value is None:
                    logger.warning(f"Environment variable not found: {var_name}")
                    return obj
                return value
            else:
                return obj
        
        self._config = substitute(self._config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path
        
        Args:
            key: Dot-separated key path (e.g., 'server.port')
            default: Default value if key not found
        
        Returns:
            Configuration value
        
        Example:
            config.get('server.port', 8000)
            config.get('mcp.name', 'template-mcp')
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def is_authentication_enabled(self) -> bool:
        """Check if authentication is enabled"""
        # Check environment variable first, then config
        env_enabled = os.getenv('AUTH_ENABLED', '').lower()
        if env_enabled in ('true', '1', 'yes'):
            return True
        if env_enabled in ('false', '0', 'no'):
            return False
        return self.get('security.authentication.enabled', False)
    
    def get_auth_token(self) -> Optional[str]:
        """Get authentication token"""
        # Check environment variable first, then config
        return os.getenv('AUTH_TOKEN') or self.get('security.authentication.bearer_token')

    def is_feedback_enabled(self) -> bool:
        """Check if feedback system is enabled"""
        return self.get('feedback.enabled', False)

    def get_feedback_config(self) -> Dict[str, Any]:
        """Get complete feedback configuration"""
        return self.get('feedback', {})

    def reload(self):
        """Reload configuration from file"""
        self._config = self._load_config()
        self._substitute_env_vars()
        logger.info("Configuration reloaded")


# Singleton instance
_config_instance = None


def get_config() -> Config:
    """Get singleton configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
