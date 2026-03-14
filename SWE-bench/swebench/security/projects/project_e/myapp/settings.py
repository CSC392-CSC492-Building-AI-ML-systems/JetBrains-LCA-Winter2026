"""Django settings for project_e."""
SECRET_KEY = "django-insecure-project-e-bench-key"
DEBUG = False
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/app/db.sqlite3",
    }
}
ROOT_URLCONF = "myapp.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
