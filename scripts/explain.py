"""Show PostgreSQL query plans for the metadata GIN index."""

import asyncio
import sys

from sqlalchemy import text

from droidpatch.db.database import engine


async def main() -> None:
    """Run EXPLAIN ANALYZE with normal and disabled sequential scans."""
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/explain.py bulletin_month VALUE")
        return

    key = sys.argv[1]
    value = sys.argv[2] if len(sys.argv) > 2 else "2024-05"

    query = text("""
        EXPLAIN ANALYZE
        SELECT id, title
        FROM documents
        WHERE metadata @> CAST(:filter AS jsonb)
    """)

    filter_value = f'{{"{key}":"{value}"}}'

    async with engine.connect() as connection:
        print("\n--- Normal query plan ---")
        result = await connection.execute(query, {"filter": filter_value})
        for row in result:
            print(row[0])

        print("\n--- Query plan with sequential scans disabled ---")
        await connection.execute(text("SET enable_seqscan = off"))
        result = await connection.execute(query, {"filter": filter_value})
        for row in result:
            print(row[0])

        await connection.execute(text("RESET enable_seqscan"))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
