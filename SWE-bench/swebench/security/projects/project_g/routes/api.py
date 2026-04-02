"""General API routes — login, register, posts."""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user

from models import User, get_db

import bcrypt

api_bp = Blueprint("api", __name__)


@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = User.get_by_username(username)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user.id,)
    ).fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        login_user(user)
        return jsonify({"status": "ok", "user_id": user.id})
    return jsonify({"error": "invalid credentials"}), 401


@api_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"status": "logged out"})


@api_bp.route("/posts", methods=["GET"])
def list_posts():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, body, category FROM posts ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api_bp.route("/posts", methods=["POST"])
@login_required
def create_post():
    data = request.get_json(force=True) or {}
    title = data.get("title", "")
    body = data.get("body", "")
    category = data.get("category", "general")
    if not title:
        return jsonify({"error": "title required"}), 400
    conn = get_db()
    conn.execute(
        "INSERT INTO posts (author_id, title, body, category) VALUES (?, ?, ?, ?)",
        (current_user.id, title, body, category),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201
