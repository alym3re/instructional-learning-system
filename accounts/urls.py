from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    CustomPasswordResetView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetDoneView,
    CustomPasswordResetCompleteView
)

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    
    path('password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name="accounts/password_change.html",
             success_url="/accounts/password_change/done/"
         ),
         name="password_change"),
    path('password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name="accounts/password_change_done.html"
         ),
         name="password_change_done"),
         
    # Password reset URLs
    path('password-reset/', 
         CustomPasswordResetView.as_view(), 
         name='password_reset'),
    path('password-reset/done/', 
         CustomPasswordResetDoneView.as_view(), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         CustomPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         CustomPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),
]
