from flask import Flask
from flask_login import LoginManager

from routes.api import api_bp
from routes.profile import profile_bp
from routes.admin import admin_bp
from routes.search import search_bp
from routes.webhooks import webhooks_bp

app = Flask(__name__)
app.secret_key = "dev-secret-only"

login_manager = LoginManager(app)
login_manager.login_view = "api.login"

app.register_blueprint(api_bp,      url_prefix="/api")
app.register_blueprint(profile_bp,  url_prefix="/profile")
app.register_blueprint(admin_bp,    url_prefix="/admin")
app.register_blueprint(search_bp,   url_prefix="/search")
app.register_blueprint(webhooks_bp, url_prefix="/webhooks")


@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.get(int(user_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
