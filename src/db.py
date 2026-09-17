import sqlite3
import os
from typing import Dict, Any, List, Tuple, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tickets.db")

def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(sql: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Safely execute a SELECT SQL query against the SQLite database.
    Returns dictionary with keys: success, columns, rows, row_count, error.
    """
    # Guardrail: Only allow SELECT or WITH queries to prevent data modification
    clean_sql = sql.strip().upper()
    if not (clean_sql.startswith("SELECT") or clean_sql.startswith("WITH")):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "Security Restriction: Only SELECT queries are permitted."
        }

    conn = None
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        columns = [description[0] for description in cursor.description] if cursor.description else []
        row_dicts = [dict(row) for row in rows]
        
        return {
            "success": True,
            "columns": columns,
            "rows": row_dicts,
            "row_count": len(row_dicts),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": str(e)
        }
    finally:
        if conn:
            conn.close()
