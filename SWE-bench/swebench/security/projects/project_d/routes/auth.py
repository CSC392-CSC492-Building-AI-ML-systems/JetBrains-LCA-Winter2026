"""Authentication routes."""
import secrets
import datetime
from flask import Blueprint, request, jsonify
from models import db, User

auth_bp = Blueprint("auth", __name__)

PASSWORD_RESET_TOKENS = {}  # token -> user_id (no expiry stored)


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    email = request.json.get("email")
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Not found"}), 404
    # BUG (CWE-640): reset token is derived from predictable data (user id +
    # static salt) and is never expired. An attacker who knows or can guess a
    # user id can forge a valid reset token, and any token issued stays valid
    # forever even after the password has already been changed.
    token = str(user.id) + "reset"           # predictable token — line 22
    PASSWORD_RESET_TOKENS[token] = user.id
    return jsonify({"reset_token": token})


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    token = request.json.get("token")
    new_password = request.json.get("password")
    user_id = PASSWORD_RESET_TOKENS.get(token)  # token never removed — line 31
    if not user_id:
        return jsonify({"error": "Invalid token"}), 400
    user = User.query.get(user_id)
    user.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "Password updated"})
