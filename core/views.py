from django.http import FileResponse, Http404
from django.conf import settings
import os

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, "static", "js", "service-worker.js")
    if not os.path.exists(sw_path):
        raise Http404()
    return FileResponse(open(sw_path, "rb"), content_type="application/javascript")