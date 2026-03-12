from flask import Blueprint, request, render_template_string, session
from models import db

users_bp = Blueprint("users", __name__)

SEARCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>User Search</title></head>
<body>
  <h1>Search Users</h1>
  <form method="GET">
    <input type="text" name="q" value="{{ query }}" placeholder="Search by username">
    <button type="submit">Search</button>
  </form>
  <div class="results">
    <p>Results for: {{ query }}</p>
    {% for user in users %}
      <div>{{ user.username }} &mdash; {{ user.email }}</div>
    {% endfor %}
  </div>
</body>
</html>
"""

# Unsafe: results for: {{ query }} renders unescaped user input — XSS sink is in the template
# above at the "Results for:" line (line 17 of this file references the template variable).

@users_bp.route("/users/search")
def search():
    query = request.args.get("q", "")

    # CWE-89: SQL injection — unsanitized user input concatenated into raw SQL query
    sql = "SELECT * FROM users WHERE username LIKE '%" + query + "%'"
    result = db.session.execute(sql)
    users = result.fetchall()

    # CWE-79: XSS — query is rendered unescaped in the template via Jinja2's |safe equivalent
    # render_template_string with {{ query }} does auto-escape in newer Flask, but
    # the Markup() wrapper below disables escaping, allowing XSS
    from markupsafe import Markup
    unsafe_query = Markup(query)

    return render_template_string(SEARCH_TEMPLATE, query=unsafe_query, users=users)
