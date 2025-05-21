from django.urls import path
from .views import service_worker

urlpatterns = [
    # ... your other url patterns ...
    path('service-worker.js', service_worker, name='service-worker.js'),
]