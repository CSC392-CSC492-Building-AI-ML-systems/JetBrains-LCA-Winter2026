import os

# CWE-798: Hardcoded secret key — line 3
SECRET_KEY = "super-secret-hardcoded-key-1234"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
