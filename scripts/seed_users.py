import asyncio
from app.core.db import db
from app.core.security import hash_password
from app.core.policy import roles_to_scopes

async def main():
    org = {"_id": "org1", "name": "FoodBridge Metro", "type": "logistics"}
    await db.orgs.update_one({"_id": org["_id"]}, {"$set": org}, upsert=True)

    user = {
        "email": "dispatcher@fb.local",
        "password_hash": hash_password("disp123"),
        "org_id": org["_id"],
        "roles": ["dispatcher"],
        "scopes": roles_to_scopes(["dispatcher"]),
        "is_active": True
    }
    await db.users.insert_one(user)
    print("✅ User seeded:", user["email"])

if __name__ == "__main__":
    asyncio.run(main())
