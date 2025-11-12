import asyncio
from app.core.db import db

async def main():
    await db.users.create_index("email", unique=True)
    await db.pickups.create_index([("org_id", 1)])
    await db.pickups.create_index([("driver_id", 1)])
    await db.pickups.create_index([("status", 1)])

if __name__ == "__main__":
    asyncio.run(main())
