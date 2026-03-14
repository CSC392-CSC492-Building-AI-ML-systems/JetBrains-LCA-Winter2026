"""Template rendering views."""
from django.http import HttpResponse
from django.template import Template, Context


def render_preview(request):
    """Render a user-supplied template string for preview.

    BUG (CWE-94): User input is passed directly to Django's Template()
    constructor and rendered. An attacker can inject template tags to read
    settings, traverse object attributes, or invoke callable properties —
    e.g. {{ request.user.is_superuser }} or file-reading gadget chains.
    """
    user_template = request.POST.get("template", "")
    t = Template(user_template)       # line 15 — user input as template source
    ctx = Context({"request": request})
    output = t.render(ctx)            # line 17 — renders attacker-controlled template
    return HttpResponse(output)
