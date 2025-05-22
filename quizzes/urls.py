from django.urls import path
from . import views

urlpatterns = [
    path('', views.grading_period_list, name='grading_period_list'),
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('toggle_period_lock/<str:period_value>/', views.toggle_period_lock, name='toggle_period_lock'),
    path('create/', views.create_quiz, name='create_quiz'),
    path('upload/', views.upload_quiz, name='upload_quiz'),
    path('<int:quiz_id>/questions/', views.add_quiz_questions, name='add_quiz_questions'),
    path('<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),
    path('results/<int:attempt_id>/', views.quiz_results, name='quiz_results'),
    path('history/', views.quiz_history, name='quiz_history'),
    path('<int:quiz_id>/questions/<int:question_id>/delete/', views.delete_question, name='delete_question'),
    path('<int:quiz_id>/questions/<int:question_id>/get/', views.get_question, name='get_question'),
    path('<int:quiz_id>/archive/', views.archive_quiz, name='archive_quiz'),
    path('<int:quiz_id>/unarchive/', views.unarchive_quiz, name='unarchive_quiz'),
    path('<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('<int:quiz_id>/', views.view_quiz, name='view_quiz'),
    path('period/<str:grading_period>/', views.quiz_list_by_period, name='quiz_list_by_period'),
    path('<int:quiz_id>/lock/', views.lock_quiz, name='lock_quiz'),
    path('<int:quiz_id>/unlock/', views.unlock_quiz, name='unlock_quiz'),
    path('<slug:slug>/delete/', views.delete_quiz, name='quiz_delete'),
    
]



