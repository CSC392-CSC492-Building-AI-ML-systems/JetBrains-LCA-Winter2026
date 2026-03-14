"""Bulk data import endpoint."""
import pickle
import base64
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def import_objects(request):
    """Accept a base64-encoded pickle blob and deserialize it.

    BUG (CWE-502): pickle.loads() on attacker-controlled data allows arbitrary
    code execution. Any class with a __reduce__ method can be instantiated,
    including os.system, subprocess.Popen, etc.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    raw = request.POST.get("data", "")
    blob = base64.b64decode(raw)
    objects = pickle.loads(blob)      # line 19 — unsafe deserialization
    return JsonResponse({"imported": len(objects)})
