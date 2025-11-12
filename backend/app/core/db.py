# app/core/db.py
from motor.motor_asyncio import AsyncIOMotorClient
from functools import lru_cache
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "foodbridge")

@lru_cache
def get_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(MONGO_URI, uuidRepresentation="standard")

def get_db():
    return get_client()[DB_NAME]
