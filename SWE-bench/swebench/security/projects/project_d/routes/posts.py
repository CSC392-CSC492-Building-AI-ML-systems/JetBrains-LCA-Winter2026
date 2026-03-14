"""Post routes."""
from flask import Blueprint, request, jsonify, g
from models import db, Post
from auth.tokens import decode_token

posts_bp = Blueprint("posts", __name__)


def get_current_user():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])
    return None


@posts_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    # BUG (CWE-352): state-changing POST endpoint has no CSRF token check.
    # Any malicious page can trigger this endpoint on behalf of an authenticated
    # user simply by submitting a form to this URL.
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": "Deleted"})  # line 26 — no csrf_token check anywhere
