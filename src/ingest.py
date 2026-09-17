import os
import csv
import sqlite3
from typing import Optional, Tuple

DEFAULT_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "support_tickets.csv")
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tickets.db")

def parse_float(val: Optional[str]) -> Optional[float]:
    """Parse string to float or return None if empty/invalid."""
    if val is None or val.strip() == "" or val.strip().lower() in ("null", "none", "nan"):
        return None
    try:
        return float(val)
    except ValueError:
        return None

def parse_int(val: Optional[str]) -> Optional[int]:
    """Parse string to int or return None if empty/invalid."""
    if val is None or val.strip() == "" or val.strip().lower() in ("null", "none", "nan"):
        return None
    try:
        return int(float(val))
    except ValueError:
        return None

def ingest_csv_to_sqlite(csv_path: str = DEFAULT_CSV_PATH, db_path: str = DEFAULT_DB_PATH) -> Tuple[int, str]:
    """
    Ingests support_tickets.csv into SQLite database.
    Creates 'tickets' table with indexed columns.
    Returns (inserted_count, db_path).
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop existing table to ensure clean slate on re-ingest
    cursor.execute("DROP TABLE IF EXISTS tickets")

    cursor.execute("""
    CREATE TABLE tickets (
        ticket_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        response_time_hrs REAL,
        resolution_time_hrs REAL,
        agent_id TEXT,
        customer_rating INTEGER,
        issue_summary TEXT,
        is_resolved INTEGER,
        is_open INTEGER,
        is_escalated INTEGER
    )
    """)

    inserted = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        tickets_to_insert = []
        for row in reader:
            status = row.get("status", "").strip()
            ticket = (
                row.get("ticket_id", "").strip(),
                row.get("created_at", "").strip(),
                row.get("category", "").strip(),
                row.get("priority", "").strip(),
                status,
                parse_float(row.get("response_time_hrs")),
                parse_float(row.get("resolution_time_hrs")),
                row.get("agent_id", "").strip() or None,
                parse_int(row.get("customer_rating")),
                row.get("issue_summary", "").strip(),
                1 if status == "Resolved" else 0,
                1 if status == "Open" else 0,
                1 if status == "Escalated" else 0
            )
            tickets_to_insert.append(ticket)

        cursor.executemany("""
        INSERT INTO tickets (
            ticket_id, created_at, category, priority, status,
            response_time_hrs, resolution_time_hrs, agent_id, customer_rating, issue_summary,
            is_resolved, is_open, is_escalated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tickets_to_insert)

        inserted = len(tickets_to_insert)

    # Create indexes for optimal query execution performance
    cursor.execute("CREATE INDEX idx_status ON tickets(status)")
    cursor.execute("CREATE INDEX idx_priority ON tickets(priority)")
    cursor.execute("CREATE INDEX idx_category ON tickets(category)")
    cursor.execute("CREATE INDEX idx_agent ON tickets(agent_id)")
    cursor.execute("CREATE INDEX idx_created_at ON tickets(created_at)")

    conn.commit()
    conn.close()

    return inserted, db_path

if __name__ == "__main__":
    count, path = ingest_csv_to_sqlite()
    print(f"Successfully ingested {count} support tickets into {path}")
