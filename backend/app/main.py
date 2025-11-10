# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_client, get_db
from app.routers import donations as donations_router
from app.routers import requests as requests_router
from app.routers import routes as routes_router
from app.routers import optimize as optimize_router
from app.routers import reports as reports_router

app = FastAPI(title="FoodBridge API")

# CORS (adjust as you like)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # touch DB + indexes
    db = get_db()
    await db.donations.create_index("status")
    await db.donations.create_index("expires")
    await db.donors.create_index([("location", "2dsphere")])

@app.on_event("shutdown")
async def shutdown():
    get_client().close()

# Include routers AFTER app is created
app.include_router(donations_router.router)
app.include_router(requests_router.router)
app.include_router(routes_router.router)     # /api/routes/*
app.include_router(optimize_router.router)   # /optimize (if you kept this)
app.include_router(reports_router.router)    # /reports/*
