"""Project D — Flask app with authentication and session flaws."""
from flask import Flask
from models import db
from routes.auth import auth_bp
from routes.posts import posts_bp
from routes.admin import admin_bp

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(posts_bp)
app.register_blueprint(admin_bp)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
