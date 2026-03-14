"""XML upload endpoint."""
from lxml import etree
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def upload_xml(request):
    """Parse an uploaded XML document and return element count.

    BUG (CWE-611): lxml's default parser has external entity expansion enabled.
    An attacker can supply an XXE payload to read local files (e.g. /etc/passwd)
    or trigger server-side request forgery via external DTD references.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    xml_data = request.body
    parser = etree.XMLParser()                   # default — XXE enabled
    tree = etree.fromstring(xml_data, parser)    # line 18 — XXE via external entity
    count = len(tree)
    return JsonResponse({"elements": count})
