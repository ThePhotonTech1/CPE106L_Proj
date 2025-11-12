# tools/seed_drivers.py
from datetime import datetime
from pymongo import MongoClient, ASCENDING
import os

URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("MONGODB_DB", "foodbridge")

client = MongoClient(URI)
db = client[DB_NAME]

# --- Drop existing drivers collection if you want to refresh it ---
db.drop_collection("drivers")

# --- Seed sample drivers ---
now = datetime.utcnow()
drivers = [
    {"name": "Juan Dela Cruz", "contact": "0917-111-2222", "vehicle": "L300", "availability": True,  "created_at": now},
    {"name": "Maria Santos",   "contact": "0917-333-4444", "vehicle": "HiAce", "availability": True,  "created_at": now},
    {"name": "Paolo Reyes",    "contact": "0917-555-6666", "vehicle": "Innova","availability": False, "created_at": now},
]

db.drivers.insert_many(drivers)

# --- Helpful indexes ---
db.drivers.create_index([("availability", ASCENDING)])
db.drivers.create_index([("name", ASCENDING)])

print("✅ Seeded drivers:")
for d in db.drivers.find({}, {"name":1,"vehicle":1,"availability":1}):
    print("-", d["name"], "|", d["vehicle"], "|", "Available" if d["availability"] else "Busy")
