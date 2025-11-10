from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URL)
db = client.foodbridge          # 👈 database name: foodbridge
routes_col = db.routes          # 👈 collection name: routes
