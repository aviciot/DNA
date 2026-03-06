"""asyncpg connection pool for portal_user"""
import logging
import asyncpg
from config import get_config

logger = logging.getLogger(__name__)


class PortalDB:
    def __init__(self):
        self.pool = None
        cfg = get_config()
        self._dsn = (
            f"postgresql://{cfg.get('database.user')}:{cfg.get('database.password')}"
            f"@{cfg.get('database.host')}:{cfg.get('database.port')}/{cfg.get('database.name')}"
        )
        self._pool_size = cfg.get('database.pool_size', 10)
        self.schema = cfg.get('database.schema', 'dna_app')

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self._dsn, min_size=2, max_size=self._pool_size
        )
        logger.info("✅ DB pool connected")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("DB pool closed")

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            await conn.execute(query, *args)

    async def health_check(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False


db = PortalDB()
