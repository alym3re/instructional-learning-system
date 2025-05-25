from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    path('', views.grading_period_exam_list, name='grading_period_exam_list'),
    path('exams/', views.exam_list, name='exam_list'),
    path('create/', views.create_exam, name='create_exam'),
    path('<int:exam_id>/questions/', views.add_exam_questions, name='add_exam_questions'),
    path('<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('results/<int:attempt_id>/', views.exam_results, name='exam_results'),
    path('history/', views.exam_history, name='exam_history'),
    path('<int:exam_id>/questions/<int:question_id>/delete/', views.delete_exam_question, name='delete_exam_question'),
    path('<int:exam_id>/archive/', views.archive_exam, name='archive_exam'),
    path('<int:exam_id>/unarchive/', views.unarchive_exam, name='unarchive_exam'),
    path('<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('<int:exam_id>/', views.view_exam, name='view_exam'),
    path('period/<str:grading_period>/', views.exam_by_period, name='exam_by_period'),
    path('<int:exam_id>/lock/', views.lock_exam, name='lock_exam'),
    path('<int:exam_id>/unlock/', views.unlock_exam, name='unlock_exam'),
    path('period/<str:grading_period>/toggle-lock/', views.toggle_period_lock, name='toggle_period_lock'),
    path('<int:exam_id>/publish/', views.publish_exam, name='publish_exam'),
    path('<int:exam_id>/unpublish/', views.unpublish_exam, name='unpublish_exam'),


]
