import sqlite3
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class JarvisMemoryDB:
    def __init__(self, db_path="jarvis_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        user_query TEXT,
                        routed_agent TEXT,
                        agent_response TEXT,
                        latency_ms INTEGER
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize SQLite DB: {e}")

    def log_interaction(self, query: str, agent: str, response: str, latency_ms: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO interactions (user_query, routed_agent, agent_response, latency_ms)
                    VALUES (?, ?, ?, ?)
                """, (query, agent, response, latency_ms))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")

db = JarvisMemoryDB()
