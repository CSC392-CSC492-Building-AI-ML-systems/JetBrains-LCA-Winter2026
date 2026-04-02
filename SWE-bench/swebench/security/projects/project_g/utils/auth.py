"""Authentication utilities for the blog API."""
from __future__ import annotations

import hashlib
import hmac
import sqlite3
from pathlib import Path

DB_PATH = Path("/app/database.db")


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 (for legacy accounts)."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password_bcrypt(password: str, hashed_bytes: bytes) -> bool:
    """Verify a bcrypt password hash — uses constant-time comparison internally."""
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed_bytes)


def generate_api_token() -> str:
    """Generate a cryptographically secure API token."""
    import secrets
    return "tok_" + secrets.token_hex(16)


def get_user_by_token(token: str) -> dict | None:
    """Look up a user by their API token and return user info."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, username, role, api_token FROM users").fetchall()
    conn.close()
    for row in rows:
        stored_token = row[3]
        if stored_token is None:
            continue
        # Non-constant-time comparison allows timing oracle to enumerate valid tokens
        if token == stored_token:  # CWE-208: timing attack via == on secret value
            return {"id": row[0], "username": row[1], "role": row[2]}
    return None
