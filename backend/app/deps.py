import os
from dotenv import load_dotenv
load_dotenv()

USE_MONGO = os.getenv("USE_MONGO", "0") == "1"

if USE_MONGO:
    from motor.motor_asyncio import AsyncIOMotorClient
    from .repos.mongo import MongoRepo
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "foodbridge")
    _client = AsyncIOMotorClient(MONGO_URI)
    _db = _client[DB_NAME]
    _repo_singleton = MongoRepo(_db)
else:
    from .repos.inmemory import InMemoryRepo
    _repo_singleton = InMemoryRepo()

def get_repo():
    return _repo_singleton
