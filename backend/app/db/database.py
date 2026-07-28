from pathlib import Path
from typing import Optional

import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "platform.db"


class Database:
    """SQLite 連線管理與 Schema 初始化"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    async def init_schema(self) -> None:
        """建立資料表與索引（若尚未存在）"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(schema_sql)
            await conn.commit()

    def connect(self) -> aiosqlite.Connection:
        """取得一個新的資料庫連線（async context manager）"""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return aiosqlite.connect(self.db_path)

    async def log_api_call(
        self, endpoint: str, response_time_ms: int, status_code: int, error_message: Optional[str] = None
    ) -> None:
        """記錄一次對外 API 呼叫之回應時間與狀態碼（需求 9.5）"""
        async with self.connect() as conn:
            await conn.execute(
                "INSERT INTO api_call_logs (endpoint, response_time_ms, status_code, error_message) VALUES (?, ?, ?, ?)",
                (endpoint, response_time_ms, status_code, error_message),
            )
            await conn.commit()
