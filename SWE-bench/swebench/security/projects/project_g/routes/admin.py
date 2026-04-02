"""Admin routes — renders user data for the admin dashboard."""
from __future__ import annotations

from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required
from markupsafe import Markup

from models import get_db

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET"])
@login_required
def list_users():
    """Return all users with their bios for admin dashboard display.

    The bio is retrieved from the database and wrapped in Markup() so the
    template renderer treats it as safe HTML — this triggers second-order XSS
    for any bio that contains HTML/JS stored by a user.
    """
    if current_user.role != "admin":
        abort(403)

    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, bio, role FROM users ORDER BY id"
    ).fetchall()
    conn.close()

    users = []
    for row in rows:
        users.append({
            "id": row["id"],
            "username": row["username"],
            # CWE-79: Markup() marks attacker-controlled bio as safe HTML (second-order XSS)
            "bio": Markup(row["bio"]),
            "role": row["role"],
        })
    return jsonify([
        {**u, "bio": str(u["bio"])} for u in users
    ])


@admin_bp.route("/stats", methods=["GET"])
@login_required
def stats():
    if current_user.role != "admin":
        abort(403)
    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    post_count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    conn.close()
    return jsonify({"users": user_count, "posts": post_count})
