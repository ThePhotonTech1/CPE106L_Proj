# app/core/indexes.py
async def ensure_indexes(db):
    # Donations & Requests
    await db.donations.create_index("status")
    await db.requests.create_index("status")
    # If you store donor/recipient names, these help
    await db.donations.create_index("donor_name")
    await db.requests.create_index("ngo_name")
    # Matches lookup
    await db.matches.create_index([("donation_id", 1)])
    await db.matches.create_index([("request_id", 1)])
