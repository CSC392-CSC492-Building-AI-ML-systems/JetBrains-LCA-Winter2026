import sqlite3
from pathlib import Path
from flask_login import UserMixin

DB_PATH = Path("/app/database.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class User(UserMixin):
    def __init__(self, id, username, role, bio="", api_token=None, webhook_url=None):
        self.id = id
        self.username = username
        self.role = role
        self.bio = bio
        self.api_token = api_token
        self.webhook_url = webhook_url

    @staticmethod
    def get(user_id):
        conn = get_db()
        row = conn.execute(
            "SELECT id, username, role, bio, api_token, webhook_url FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return User(row["id"], row["username"], row["role"], row["bio"],
                    row["api_token"], row["webhook_url"])

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        row = conn.execute(
            "SELECT id, username, role, bio, api_token, webhook_url FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return User(row["id"], row["username"], row["role"], row["bio"],
                    row["api_token"], row["webhook_url"])
