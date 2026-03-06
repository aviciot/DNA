"""Configuration loader with env var substitution"""
import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            env = os.getenv('ENV', 'default')
            config_file = {'dev': 'settings.dev.yaml', 'prod': 'settings.prod.yaml'}.get(env, 'settings.yaml')
            config_path = Path(__file__).parent / "config" / config_file
        self.config_path = Path(config_path)
        self._config = self._load()
        self._substitute_env_vars()

    def _load(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _substitute_env_vars(self):
        def sub(obj):
            if isinstance(obj, dict):
                return {k: sub(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [sub(i) for i in obj]
            if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                return os.getenv(obj[2:-1], obj)
            return obj
        self._config = sub(self._config)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        val = self._config
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k)
            if val is None:
                return default
        return val

    def is_authentication_enabled(self) -> bool:
        env = os.getenv('AUTH_ENABLED', '').lower()
        if env in ('true', '1', 'yes'):
            return True
        if env in ('false', '0', 'no'):
            return False
        return self.get('security.authentication.enabled', False)

    def get_api_keys(self) -> Dict[str, str]:
        keys = self.get('security.authentication.api_keys', [])
        return {k['key']: k['name'] for k in keys}


_instance = None

def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
