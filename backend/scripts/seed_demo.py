import asyncio
from app.core.db import db

async def main():
    # wipe demo rows if they exist
    await db.donors.delete_many({"_id":{"$in":["D1"]}})
    await db.recipients.delete_many({"_id":{"$in":["R1","R2"]}})

    await db.donors.insert_one({
        "_id": "D1",
        "org_id": "org1",
        "name": "Donor A",
        "coord": [120.98, 14.60],     # [lon, lat]
        "categories": ["produce","bread"],
        "qty": 25
    })
    await db.recipients.insert_many([
        {"_id":"R1","org_id":"org1","name":"Recipient One","coord":[121.00,14.61],"needs":["produce"],"capacity":50},
        {"_id":"R2","org_id":"org1","name":"Recipient Two","coord":[121.03,14.62],"needs":["bread"],"capacity":10},
    ])
    print("Seeded: D1, R1, R2")

if __name__ == "__main__":
    asyncio.run(main())
