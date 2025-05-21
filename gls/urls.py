
from django.views.generic import TemplateView

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('core.urls')),

    path('admin/', admin.site.urls), 
    path('', TemplateView.as_view(template_name='index.html'), name='index'), 
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('lessons/', include(('lessons.urls', 'lessons'), namespace='lessons')),
    path('quizzes/', include(('quizzes.urls', 'quizzes'), namespace='quizzes')),
    path('exams/', include(('exams.urls', 'exams'), namespace='exams')),
    path('students/', include('students.urls', namespace='students')),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
