"""Measure the app connection pool after 50 read-only HTTP requests.

Run while a usable DATABASE_URL is configured:
    uv run python scripts/measure_pool.py
"""

import asyncio

import httpx

from droidpatch.api.main import create_app
from droidpatch.db.database import engine

REQUEST_COUNT = 50


async def send_requests(client: httpx.AsyncClient) -> int:
    """Issue quick read-only readiness requests and fail on HTTP errors."""
    for _ in range(REQUEST_COUNT):
        response = await client.get("/ready")
        response.raise_for_status()
    return REQUEST_COUNT


async def main() -> None:
    """Use an in-process HTTPX client so requests and pool share one engine."""
    app = create_app()
    async with app.router.lifespan_context(app):
        print(f"pool_before={engine.pool.status()}")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://droidpatch") as client:
            completed = await send_requests(client)
        print(f"requests={completed}")
        print(f"pool_after={engine.pool.status()}")


if __name__ == "__main__":
    asyncio.run(main())
