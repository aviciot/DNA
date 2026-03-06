import asyncpg
from fastapi import Cookie, HTTPException
from app.config import settings

_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def validate_token(portal_token: str = Cookie(None)) -> dict:
    """Dependency: validates httpOnly cookie token against customer_portal_access."""
    if not portal_token:
        raise HTTPException(status_code=401, detail="No session token")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT cpa.token, cpa.customer_id, cpa.expires_at,
                       c.name AS customer_name, c.contact_person,
                       c.contact_email, c.description AS customer_description
                FROM {settings.database_app_schema}.customer_portal_access cpa
                JOIN {settings.database_app_schema}.customers c ON c.id = cpa.customer_id
                WHERE cpa.token = $1 AND cpa.expires_at > NOW()""",
            portal_token,
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        # Default plan: customer's first active plan
        plan_row = await conn.fetchrow(
            f"""SELECT cip.id AS plan_id, cip.plan_name, cip.target_completion_date,
                       iso.code AS iso_code, iso.name AS iso_name
                FROM {settings.database_app_schema}.customer_iso_plans cip
                JOIN {settings.database_app_schema}.iso_standards iso ON iso.id = cip.iso_standard_id
                WHERE cip.customer_id = $1
                ORDER BY cip.created_at
                LIMIT 1""",
            row["customer_id"],
        )

        await conn.execute(
            f"UPDATE {settings.database_app_schema}.customer_portal_access"
            f" SET last_used_at = NOW() WHERE token = $1",
            portal_token,
        )

    session = dict(row)
    if plan_row:
        session.update(dict(plan_row))
    else:
        session.update({
            "plan_id": None, "plan_name": None,
            "iso_code": None, "iso_name": None,
            "target_completion_date": None,
        })
    return session


async def log_activity(event: str, token: str, customer_id: int,
                       detail: dict | None = None, ip: str | None = None):
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""INSERT INTO {settings.database_app_schema}.portal_activity_log
                (event, token, customer_id, detail, ip_address)
                VALUES ($1, $2, $3, $4::jsonb, $5)""",
            event, token, customer_id,
            json.dumps(detail or {}), ip,
        )
