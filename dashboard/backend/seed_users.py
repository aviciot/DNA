import asyncio
from app.database import get_db_pool

async def seed():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        emails = [
            ('avicoiot@gmail.com', 'Avico'),
            ('avico78@gmail.com', 'Avico'),
            ('yossidana1@gmail.com', 'Yossi'),
        ]
        for email, name in emails:
            await conn.execute(
                """INSERT INTO auth.users (email, full_name, role, is_active, password_hash)
                   VALUES ($1, $2, $3, true, '')
                   ON CONFLICT (email) DO NOTHING""",
                email, name, 'admin'
            )
            print(f'Provisioned: {email}')
    print('Done')

asyncio.run(seed())
