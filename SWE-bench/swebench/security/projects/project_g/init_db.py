"""Database initialisation — run once during Docker image build."""
import sqlite3
import bcrypt

conn = sqlite3.connect("database.db")
conn.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    bio TEXT DEFAULT '',
    role TEXT DEFAULT 'user',
    api_token TEXT UNIQUE,
    webhook_url TEXT
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT DEFAULT 'general'
);
""")
pw = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
conn.execute(
    "INSERT OR IGNORE INTO users (username, password_hash, role, api_token) "
    "VALUES ('admin', ?, 'admin', 'tok_admin_abc123')",
    (pw,),
)
conn.execute(
    "INSERT OR IGNORE INTO users (username, password_hash, api_token) "
    "VALUES ('alice', ?, 'tok_alice_xyz789')",
    (pw,),
)
conn.execute(
    "INSERT OR IGNORE INTO posts (author_id, title, body, category) "
    "VALUES (2, 'Hello World', 'First post', 'general')"
)
conn.commit()
conn.close()
print("Database initialised.")
