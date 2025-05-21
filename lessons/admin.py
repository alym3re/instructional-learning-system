from django.contrib import admin
from .models import Lesson, LessonProgress, LessonAccess

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'grading_period', 'upload_date', 'is_active', 'is_featured', 'view_count')
    list_filter = ('grading_period', 'is_active', 'is_featured')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('upload_date', 'last_updated', 'view_count', 'uploaded_by')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'description', 'grading_period')
        }),
        ('Media', {
            'fields': ('file', 'thumbnail')
        }),
        ('Metadata', {
            'fields': ('uploaded_by',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Statistics', {
            'fields': ('upload_date', 'last_updated', 'view_count'),
            'classes': ('collapse',)
        }),
    )
    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'completed', 'last_viewed')
    list_filter = ('completed', 'last_viewed')
    search_fields = ('user__username', 'lesson__title')
    readonly_fields = ('last_viewed',)

@admin.register(LessonAccess)
class LessonAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'access_type', 'timestamp')
    list_filter = ('access_type', 'timestamp', 'lesson')
    search_fields = ('user__username', 'lesson__title')
    readonly_fields = ('timestamp',)