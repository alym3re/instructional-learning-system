from django.contrib import admin
from .models import StudentProgress, ActivityLog

@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('last_active',)

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__username',)
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
