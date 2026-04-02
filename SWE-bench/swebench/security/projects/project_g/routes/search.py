"""Post search endpoint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from utils.db import execute_search

search_bp = Blueprint("search", __name__)


@search_bp.route("/posts", methods=["GET"])
def search_posts():
    """Search posts by category or title keyword.

    Query params:
      category  - filter by category (e.g. "general")
      keyword   - substring match on title
    """
    category = request.args.get("category", "")
    keyword = request.args.get("keyword", "")

    # Build filter fragment from user-supplied query parameters
    conditions = []
    if category:
        # Intended: restrict to a category — but value is not sanitized
        conditions.append(f"category = '{category}'")
    if keyword:
        conditions.append(f"title LIKE '%{keyword}%'")

    filter_clause = " AND ".join(conditions) if conditions else "1=1"

    # The raw filter_clause is passed directly to execute_search()
    # Cross-file SQL injection: user input flows from here → utils/db.py:execute_search
    results = execute_search(filter_clause)
    return jsonify(results)
