"""Database query utilities."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("/app/database.db")


def parameterized_query(sql: str, params: tuple = ()) -> list:
    """Execute a parameterized query safely — always use this for user input."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def execute_write(sql: str, params: tuple = ()) -> None:
    """Execute a write (INSERT/UPDATE/DELETE) with parameters."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def execute_search(filter_clause: str) -> list:
    """Execute a posts search with the provided filter clause.

    The filter_clause is expected to be a validated SQL fragment built by the
    search route. Results are returned as a list of dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQL injection: filter_clause is constructed from user input in routes/search.py
    query = f"SELECT id, title, body, category FROM posts WHERE {filter_clause}"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]
