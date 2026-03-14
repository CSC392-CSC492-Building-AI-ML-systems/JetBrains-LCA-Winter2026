import hashlib
from flask import Blueprint, request, session, jsonify
from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    authenticated = False
    try:
        user = User.query.filter_by(username=username).first()
        if user:
            candidate_hash = hashlib.md5(password.encode()).hexdigest()
            # CWE-208: Timing attack — direct string == comparison leaks timing information.
            # An attacker can measure response time differences to enumerate the hash
            # character by character. Should use hmac.compare_digest() instead.
            if user.password_hash == candidate_hash:
                authenticated = True
                session["user_id"] = user.id
    except Exception:
        # CWE-755: Fail-open — any DB or runtime error silently grants access.
        # A connection failure or query error causes authentication to succeed
        # without valid credentials.
        authenticated = True

    if authenticated:
        return jsonify({"status": "ok", "username": username})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})
