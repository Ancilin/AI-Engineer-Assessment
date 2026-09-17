import os
import sqlite3
import pytest
from src.ingest import ingest_csv_to_sqlite
from src.db import execute_query, DEFAULT_DB_PATH

def test_csv_ingestion():
    """Verify that support_tickets.csv is ingested into SQLite correctly with 500 rows."""
    count, db_path = ingest_csv_to_sqlite()
    assert count == 500
    assert os.path.exists(db_path)

    res = execute_query("SELECT COUNT(*) as count FROM tickets")
    assert res["success"] is True
    assert res["rows"][0]["count"] == 500

def test_schema_columns():
    """Verify all required schema columns exist in tickets table."""
    res = execute_query("SELECT * FROM tickets LIMIT 1")
    assert res["success"] is True
    expected_cols = [
        "ticket_id", "created_at", "category", "priority", "status",
        "response_time_hrs", "resolution_time_hrs", "agent_id", "customer_rating", "issue_summary"
    ]
    for col in expected_cols:
        assert col in res["columns"]
