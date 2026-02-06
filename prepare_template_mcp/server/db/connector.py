"""
Database Connector Template (OPTIONAL)
======================================
Example pattern for database connections with connection pooling

Uncomment and adapt for your database:
- Oracle: use oracledb
- PostgreSQL: use asyncpg
- MySQL: use aiomysql
- SQL Server: use aioodbc
"""

import logging
# import asyncpg  # Example for PostgreSQL

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    Template for database connection with connection pooling
    
    Features:
    - Connection pooling for performance
    - Async/await support
    - Automatic reconnection
    - Health check support
    """
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str, pool_size: int = 10):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_size = pool_size
        self.pool = None
    
    async def connect(self):
        """Initialize connection pool"""
        try:
            # Example for PostgreSQL (uncomment and adapt)
            # self.pool = await asyncpg.create_pool(
            #     host=self.host,
            #     port=self.port,
            #     database=self.database,
            #     user=self.user,
            #     password=self.password,
            #     min_size=2,
            #     max_size=self.pool_size
            # )
            logger.info(f"Database pool created: {self.database}@{self.host}")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            # await self.pool.close()
            logger.info("Database pool closed")
    
    async def execute_query(self, query: str, params: tuple = None):
        """
        Execute a query and return results
        
        Args:
            query: SQL query to execute
            params: Query parameters (prevents SQL injection)
        
        Returns:
            List of rows as dicts
        """
        if not self.pool:
            raise RuntimeError("Database not connected - call connect() first")
        
        try:
            # Example for PostgreSQL
            # async with self.pool.acquire() as conn:
            #     rows = await conn.fetch(query, *params if params else [])
            #     return [dict(row) for row in rows]
            
            # Placeholder return
            return []
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if database connection is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.pool:
                return False
            
            # Example health check query
            # result = await self.execute_query("SELECT 1")
            # return len(result) > 0
            
            return True
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Usage example in config.py:
# from db.connector import DatabaseConnector
# 
# db = DatabaseConnector(
#     host=config.get('database.host'),
#     port=config.get('database.port'),
#     database=config.get('database.name'),
#     user=config.get('database.user'),
#     password=config.get('database.password'),
#     pool_size=config.get('database.pool_size', 10)
# )
# 
# # In server.py startup:
# await db.connect()
# 
# # In tools:
# @mcp.tool()
# async def query_data():
#     rows = await db.execute_query("SELECT * FROM users WHERE active = $1", (True,))
#     return rows
