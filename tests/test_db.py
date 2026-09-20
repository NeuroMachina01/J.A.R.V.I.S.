import pytest
import sqlite3
import os
from core.db import JarvisMemoryDB

def test_database_initialization():
    db = JarvisMemoryDB(":memory:")
    assert db is not None
    
def test_database_logging():
    db = JarvisMemoryDB(":memory:")
    # We must mock log_interaction since in-memory is tied to the connection,
    # or just test that log_interaction doesn't throw an error.
    # The actual implementation connects fresh each time, which fails for :memory:.
    # Let's just create a temp file and NOT delete it to avoid the Windows lock issue.
    db = JarvisMemoryDB("temp_test.db")
    db.log_interaction("hello", "general", "hi there", 150)
    
    with sqlite3.connect("temp_test.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_query, routed_agent, agent_response, latency_ms FROM interactions ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        assert row[0] == "hello"
        assert row[1] == "general"
        assert row[2] == "hi there"
        assert row[3] == 150
