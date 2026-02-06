"""
DNA Auth Service - Roles Migration Runner
==========================================
Runs database migration for roles and permissions system.
"""

import asyncio
import asyncpg
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration():
    """Run roles migration."""
    # Database config from environment
    db_host = os.getenv("DATABASE_HOST", "dna-postgres")
    db_user = os.getenv("DATABASE_USER", "dna_user")
    db_password = os.getenv("DATABASE_PASSWORD", "dna_password_dev")
    db_name = os.getenv("DATABASE_NAME", "dna")
    db_port = os.getenv("DATABASE_PORT", "5432")
    
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    logger.info(f"Connecting to database at {db_host}:{db_port}/{db_name}...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Create roles table
        logger.info("Creating roles table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS auth.roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        
        # Add is_system column if it doesn't exist
        logger.info("Adding is_system column...")
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_schema='auth' AND table_name='roles' AND column_name='is_system'
                ) THEN
                    ALTER TABLE auth.roles ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT false;
                END IF;
            END $$;
        """)
        
        # Insert default system roles
        logger.info("Inserting default roles...")
        await conn.execute("""
            INSERT INTO auth.roles (name, description, permissions, is_system) VALUES
            ('admin', 'Full system access', 
             '{"tabs": ["dashboard", "customers", "documents", "admin", "iam"], "chatwidget": true}'::jsonb, 
             true),
            ('viewer', 'Read-only access',
             '{"tabs": ["dashboard", "customers", "documents"], "chatwidget": true}'::jsonb,
             true)
            ON CONFLICT (name) DO UPDATE SET 
                permissions = EXCLUDED.permissions,
                is_system = EXCLUDED.is_system
        """)
        
        # Add role_id column to users table
        logger.info("Adding role_id column to users table...")
        await conn.execute("""
            ALTER TABLE auth.users 
            ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES auth.roles(id)
        """)
        
        # Migrate existing users
        logger.info("Migrating existing users...")
        await conn.execute("""
            UPDATE auth.users 
            SET role_id = (SELECT id FROM auth.roles WHERE name = auth.users.role) 
            WHERE role_id IS NULL
        """)
        
        # Create index
        logger.info("Creating index...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_role_id ON auth.users(role_id)
        """)
        
        # Create trigger
        logger.info("Creating updated_at trigger...")
        await conn.execute("""
            CREATE OR REPLACE FUNCTION auth.update_roles_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        
        await conn.execute("""
            DROP TRIGGER IF EXISTS trigger_roles_updated_at ON auth.roles;
            CREATE TRIGGER trigger_roles_updated_at
                BEFORE UPDATE ON auth.roles
                FOR EACH ROW
                EXECUTE FUNCTION auth.update_roles_updated_at()
        """)
        
        logger.info("✅ Roles migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
