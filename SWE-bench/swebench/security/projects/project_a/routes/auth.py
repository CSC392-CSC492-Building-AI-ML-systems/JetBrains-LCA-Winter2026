from flask import Blueprint, request, session, redirect, url_for, render_template_string
from werkzeug.security import check_password_hash
from models import db, User

auth_bp = Blueprint("auth", __name__)

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
  <h1>Login</h1>
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
</body>
</html>
"""


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("users.search"))
        error = "Invalid credentials."
    return render_template_string(LOGIN_TEMPLATE, error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
