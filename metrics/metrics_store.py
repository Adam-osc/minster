from typing import Optional

import sqlite3


class MetricsStore:
    def __init__(self, db_path: str):
        self._conn: sqlite3.Connection = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL;")

        self._conn.execute("""
        CREATE TABLE IF NOT EXISTS basecalled_reads (
          read_id      TEXT,
          final_class  TEXT,
          length       INTEGER,
          timestamp    TEXT
        )
        """)
        self._conn.execute("""
        CREATE TABLE IF NOT EXISTS classified_reads (
          read_id        TEXT,
          inferred_class TEXT,
          timestamp    TEXT
        )
        """)
        self._conn.commit()

    def record_basecalled_reads(self, read_id: str, final_class: str, length: int, timestamp: str):
        self._conn.execute(
            "INSERT INTO basecalled_reads (read_id, final_class, length, timestamp) VALUES (?, ?, ?, ?)",
            (read_id, final_class, length, timestamp)
        )
        self._conn.commit()

    def record_classified_reads(self, read_id: str, inferred_class: Optional[str], timestamp: str):
        self._conn.execute(
            "INSERT INTO classified_reads (read_id, inferred_class, timestamp) VALUES (?, ?, ?)",
            (read_id, inferred_class, timestamp)
        )
        self._conn.commit()

    def close(self):
        self._conn.commit()
        self._conn.close()
