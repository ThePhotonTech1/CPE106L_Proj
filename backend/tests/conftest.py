# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from app.main import app

@pytest.fixture(scope="session")
def anyio_backend():
    # keep AnyIO on asyncio for the whole test session
    return "asyncio"

@pytest.fixture(scope="session")
async def test_client():
    # Start FastAPI lifespan once for the whole session
    async with LifespanManager(app):
        transport = ASGITransport(app=app, raise_app_exceptions=True)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
