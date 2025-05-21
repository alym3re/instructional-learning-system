from django.urls import path
from . import views
from .views import LessonUpdateView

app_name = "lessons"

urlpatterns = [
    path('', views.grading_period_list, name='grading_period_list'),
    path('period/<str:grading_period>/', views.lesson_list_by_period, name='lesson_list_by_period'),
    path('upload/', views.upload_lesson, name='upload_lesson'),
    path('<slug:slug>/', views.view_lesson, name='view_lesson'),
    path('<slug:slug>/edit/', LessonUpdateView.as_view(), name='lesson_edit'),
    path('<slug:slug>/complete/', views.mark_completed, name='mark_completed'),
    path('<slug:slug>/download/', views.download_lesson_file, name='download_lesson_file'),
    path('<slug:slug>/archive/', views.archive_lesson, name='lesson_archive'),
    path('<slug:slug>/unarchive/', views.unarchive_lesson, name='lesson_unarchive'),
    path('<slug:slug>/read/', views.read_file, name='read_file'),
    path('admin/lesson-access/', views.admin_lesson_access_report, name='lesson_access_report'),
    path('admin/period-lock-toggle/<str:grading_period>/', views.toggle_period_lock, name='toggle_period_lock'),
    path('<slug:slug>/delete/', views.delete_lesson, name='lesson_delete'),

]