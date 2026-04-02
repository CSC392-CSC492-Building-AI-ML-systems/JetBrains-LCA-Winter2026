"""Webhook management routes."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import get_db

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/set", methods=["POST"])
@login_required
def set_webhook():
    """Store a webhook URL for post-event notifications."""
    data = request.get_json(force=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    conn = get_db()
    conn.execute(
        "UPDATE users SET webhook_url = ? WHERE id = ?",
        (url, current_user.id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "webhook set", "url": url})


@webhooks_bp.route("/", methods=["GET"])
@login_required
def get_webhook():
    """Return the current user's webhook URL."""
    return jsonify({"url": current_user.webhook_url})
