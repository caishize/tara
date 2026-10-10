"""
One-time script to clean up all insight-related data.

Tables cleaned (in dependency order):
  - insight_entities (FK → insights, CASCADE)
  - insight_feedbacks (FK → memory_insights, CASCADE)
  - insights (unified)
  - memory_insights (legacy)
  - user_insights (legacy, briefing module)
  - tracked_threads (engine v2)

Usage:
  cd backend && python -m scripts.cleanup_insights
"""
import asyncio
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text
from src.db.session import engine as async_engine


TABLES_TO_CLEAN = [
    # Children first (even though CASCADE would handle it, be explicit)
    "insight_entities",
    "insight_feedbacks",
    # Parent tables
    "insights",
    "memory_insights",
    "user_insights",
    "tracked_threads",
]


async def cleanup():
    async with async_engine.begin() as conn:
        for table in TABLES_TO_CLEAN:
            # Check if table exists
            result = await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_name = :name"
                    ")"
                ),
                {"name": table},
            )
            exists = result.scalar()
            if not exists:
                print(f"  SKIP  {table} (does not exist)")
                continue

            # Count before delete
            count_result = await conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            count = count_result.scalar()

            # Truncate with cascade for safety
            await conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
            print(f"  CLEAN {table}: {count} rows removed")

    # Dispose engine to close connections
    await async_engine.dispose()
    print("\nDone. All insight data cleaned up.")


if __name__ == "__main__":
    import os

    db_host = os.environ.get("DATABASE_HOST", "unknown")
    print(f"Target database: {db_host}")
    print(f"Tables to truncate: {', '.join(TABLES_TO_CLEAN)}\n")
    confirm = input("Type 'yes' to proceed: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        sys.exit(1)
    print()
    asyncio.run(cleanup())
