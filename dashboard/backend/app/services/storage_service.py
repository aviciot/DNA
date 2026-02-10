"""
Storage Service for Customer Files
===================================

Manages customer file storage across different providers (local, Google Drive, S3).
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class StorageProvider:
    """Base class for storage providers"""

    async def initialize(self, customer_id: int, customer_name: str) -> str:
        """Initialize storage for a customer. Returns storage path."""
        raise NotImplementedError

    async def upload_file(self, path: str, file_data: bytes, filename: str) -> str:
        """Upload file to storage. Returns full path."""
        raise NotImplementedError

    async def download_file(self, path: str) -> bytes:
        """Download file from storage."""
        raise NotImplementedError

    async def delete_file(self, path: str) -> bool:
        """Delete file from storage."""
        raise NotImplementedError

    async def list_files(self, path: str) -> list:
        """List files in path."""
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider"""

    def __init__(self, base_path: str = None):
        """
        Initialize local storage provider.

        Args:
            base_path: Base directory for customer storage.
                      Defaults to /var/dna/storage/customers (Linux/Docker)
                      or C:/dna/storage/customers (Windows)
        """
        if base_path is None:
            if os.name == 'nt':  # Windows
                base_path = "C:/dna/storage/customers"
            else:  # Linux/Docker
                base_path = "/var/dna/storage/customers"

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageProvider initialized with base_path: {self.base_path}")

    def _sanitize_name(self, name: str) -> str:
        """Sanitize customer name for folder name"""
        # Convert to lowercase, replace spaces with underscores
        sanitized = name.lower().strip()
        sanitized = re.sub(r'[^\w\s-]', '', sanitized)  # Remove special chars
        sanitized = re.sub(r'[\s]+', '_', sanitized)  # Replace spaces with underscore
        return sanitized

    async def initialize(self, customer_id: int, customer_name: str) -> str:
        """
        Initialize storage folders for a customer.

        Creates folder structure:
        customers/{customer_id}_{sanitized_name}/
            ├── documents/
            ├── evidence/
            ├── exports/
            └── temp/

        Returns:
            str: Full path to customer storage root
        """
        sanitized_name = self._sanitize_name(customer_name)
        customer_folder = f"{customer_id}_{sanitized_name}"
        customer_path = self.base_path / customer_folder

        # Create main folder
        customer_path.mkdir(parents=True, exist_ok=True)

        # Create subfolders
        subfolders = ['documents', 'evidence', 'exports', 'temp']
        for folder in subfolders:
            (customer_path / folder).mkdir(exist_ok=True)

        logger.info(f"Initialized storage for customer {customer_id} at {customer_path}")

        return str(customer_path)

    async def upload_file(self, path: str, file_data: bytes, filename: str) -> str:
        """
        Upload file to storage.

        Args:
            path: Relative path within customer storage (e.g., "evidence/task_123")
            file_data: File content as bytes
            filename: Original filename

        Returns:
            str: Full path to uploaded file
        """
        file_path = Path(path) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"Uploaded file: {file_path} ({len(file_data)} bytes)")

        return str(file_path)

    async def download_file(self, path: str) -> bytes:
        """Download file from storage"""
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(file_path, 'rb') as f:
            data = f.read()

        logger.info(f"Downloaded file: {file_path} ({len(data)} bytes)")

        return data

    async def delete_file(self, path: str) -> bool:
        """Delete file from storage"""
        file_path = Path(path)

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return True

        return False

    async def list_files(self, path: str) -> list:
        """List files in path"""
        dir_path = Path(path)

        if not dir_path.exists():
            return []

        files = []
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        return files


class GoogleDriveProvider(StorageProvider):
    """Google Drive storage provider (future implementation)"""

    async def initialize(self, customer_id: int, customer_name: str) -> str:
        raise NotImplementedError("Google Drive storage not yet implemented")


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider (future implementation)"""

    async def initialize(self, customer_id: int, customer_name: str) -> str:
        raise NotImplementedError("S3 storage not yet implemented")


class StorageService:
    """
    Storage service for managing customer files across different providers.
    """

    _providers = {
        'local': LocalStorageProvider,
        'google_drive': GoogleDriveProvider,
        's3': S3StorageProvider,
    }

    @classmethod
    def get_provider(cls, storage_type: str, config: Optional[Dict[str, Any]] = None) -> StorageProvider:
        """
        Get storage provider instance.

        Args:
            storage_type: Type of storage ('local', 'google_drive', 's3')
            config: Optional configuration for the provider

        Returns:
            StorageProvider: Instance of the storage provider
        """
        if storage_type not in cls._providers:
            raise ValueError(f"Unknown storage type: {storage_type}")

        provider_class = cls._providers[storage_type]

        if storage_type == 'local':
            base_path = config.get('base_path') if config else None
            return provider_class(base_path=base_path)
        else:
            return provider_class()

    @classmethod
    async def initialize_customer_storage(
        cls,
        customer_id: int,
        customer_name: str,
        storage_type: str = 'local',
        storage_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initialize storage for a customer.

        Args:
            customer_id: Customer ID
            customer_name: Customer name
            storage_type: Type of storage ('local', 'google_drive', 's3')
            storage_config: Optional storage configuration

        Returns:
            str: Storage path for the customer
        """
        provider = cls.get_provider(storage_type, storage_config)
        storage_path = await provider.initialize(customer_id, customer_name)

        logger.info(f"Initialized {storage_type} storage for customer {customer_id}: {storage_path}")

        return storage_path


# Export for convenience
storage_service = StorageService()
