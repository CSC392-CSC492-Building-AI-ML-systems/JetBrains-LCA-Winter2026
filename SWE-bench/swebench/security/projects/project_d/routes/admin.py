"""Admin routes — role check is client-supplied, not server-enforced."""
from flask import Blueprint, request, jsonify
from models import db, User
from auth.tokens import decode_token

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/users", methods=["GET"])
def list_users():
    # BUG (CWE-862): The role check reads from the request body (client-controlled)
    # instead of the server-side JWT or session. Any client can send
    # {"role": "admin"} and bypass the check entirely.
    role = request.json.get("role") if request.json else None  # line 14 — client-supplied
    if role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    users = User.query.all()
    return jsonify([{"id": u.id, "email": u.email} for u in users])


@admin_bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    role = request.json.get("role") if request.json else None  # line 22 — same flaw
    if role != "admin":
        return jsonify({"error": "Forbidden"}), 403
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Deleted"})
