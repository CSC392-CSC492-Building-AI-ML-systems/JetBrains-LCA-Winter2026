"""Start the Django development server."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")

import django
django.setup()

from django.core.management import call_command
call_command("migrate", "--run-syncdb", verbosity=0)

from django.core.management.commands.runserver import Command as runserver
import subprocess
subprocess.run([sys.executable, "manage.py", "runserver", "0.0.0.0:8000"])
