from django.contrib import admin
from .models import StudentProgress, Badge, ActivityLog

@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'total_xp', 'last_active')
    list_filter = ('level',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('last_active',)

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'xp_reward', 'condition')
    search_fields = ('name', 'condition')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'xp_earned', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__username',)
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'