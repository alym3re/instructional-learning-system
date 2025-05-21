from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from .forms import RegistrationForm

class CustomUserAdmin(UserAdmin):
    add_form = RegistrationForm
    model = User
    list_display = ('username', 'student_id', 'email', 'first_name', 'last_name', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('student_id', 'first_name', 'middle_name', 'last_name', 'email', 'profile_pic')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Gamification', {'fields': ('points', 'level')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('student_id', 'username', 'first_name', 'middle_name', 'last_name', 'email', 'profile_pic', 'password1', 'password2'),
        }),
    )
    search_fields = ('username', 'student_id', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

admin.site.register(User, CustomUserAdmin)