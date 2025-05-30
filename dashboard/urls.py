from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('download_rankings_docx/<str:period_value>/', views.download_rankings_docx, name='download_rankings_docx'),
    path('edit_total_days/', views.edit_total_days, name='edit_total_days'),
    path('edit_days_present/', views.edit_days_present, name='edit_days_present'),


]
