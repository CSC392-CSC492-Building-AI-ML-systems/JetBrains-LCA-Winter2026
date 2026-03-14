"""User management API."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
import json


@csrf_exempt
def update_user(request, user_id):
    """Update user fields from JSON body.

    BUG (CWE-915): The entire request dict is applied to the user model without
    filtering. An attacker can supply {"is_staff": true, "is_superuser": true}
    to escalate their own privileges.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    data = json.loads(request.body)
    user = User.objects.get(pk=user_id)
    for key, value in data.items():   # line 20 — mass assignment, no field allowlist
        setattr(user, key, value)
    user.save()
    return JsonResponse({"updated": user_id})
