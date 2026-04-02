"""User profile routes."""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from models import get_db

profile_bp = Blueprint("profile", __name__)

# Characters that look dangerous but the sanitizer handles XSS
_DISALLOWED_CHARS = {"<script", "javascript:", "onerror="}


def _sanitize_bio(text: str) -> str:
    """Remove obviously dangerous patterns from bio text.

    Note: this only catches the most naive XSS patterns and is NOT
    a comprehensive sanitizer.
    """
    lower = text.lower()
    for pattern in _DISALLOWED_CHARS:
        if pattern in lower:
            return ""  # reject outright if obvious pattern found
    return text


@profile_bp.route("/", methods=["GET"])
@login_required
def get_profile():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "bio": current_user.bio,
        "role": current_user.role,
    })


@profile_bp.route("/update", methods=["POST"])
@login_required
def update_profile():
    """Update the current user's bio.

    The bio is stored as-is in the database. _sanitize_bio is applied but only
    catches naive patterns; a crafted payload like <img src=x onerror=alert(1)>
    passes through and gets stored. The rendering in admin.py is where the XSS
    is triggered (second-order / stored XSS).
    """
    data = request.get_json(force=True) or {}
    bio = data.get("bio", "")

    # Sanitizer appears to protect against XSS but is easily bypassed
    bio = _sanitize_bio(bio)

    conn = get_db()
    # Bio stored with parameterized query — storage is "safe" but content is attacker-controlled
    conn.execute(
        "UPDATE users SET bio = ? WHERE id = ?",
        (bio, current_user.id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})
