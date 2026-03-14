from flask import Blueprint, request, session, jsonify
from models import db, User

users_bp = Blueprint("users", __name__)


def _require_login():
    return session.get("user_id") is not None


@users_bp.route("/api/users", methods=["GET"])
def list_users():
    if not _require_login():
        return jsonify({"error": "Unauthorized"}), 401
    users = User.query.all()
    return jsonify(
        [{"id": u.id, "username": u.username, "email": u.email} for u in users]
    )
