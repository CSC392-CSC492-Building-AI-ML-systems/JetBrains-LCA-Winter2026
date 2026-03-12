import hashlib
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)

    def set_password(self, password: str) -> None:
        # CWE-916: MD5 is cryptographically broken and unsuitable for password hashing
        self.password_hash = hashlib.md5(password.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.md5(password.encode()).hexdigest()

    def __repr__(self):
        return f"<User {self.username}>"
