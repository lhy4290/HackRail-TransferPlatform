import pytest

from app.db.database import Database


@pytest.mark.asyncio
async def test_init_schema_creates_tables(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.init_schema()
    async with db.connect() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] async for row in cursor}
    expected = {
        "stations",
        "transfer_stations",
        "network_edges",
        "delay_history",
        "api_call_logs",
        "service_alerts_cache",
    }
    assert expected.issubset(tables)
