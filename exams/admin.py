from django.contrib import admin
from .models import Exam, ExamQuestion, ExamAnswer, ExamAttempt, ExamUserAnswer

class ExamAnswerInline(admin.TabularInline):
    model = ExamAnswer
    extra = 2
    min_num = 2

class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 1
    show_change_link = True

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'grading_period', 'created_by', 'created_at', 'question_count'
    )
    list_filter = ('grading_period', 'created_at')
    search_fields = ('title', 'description', 'created_by__username')
    inlines = [ExamQuestionInline]
    readonly_fields = ('view_count', 'created_at', 'updated_at')

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'

@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'exam', 'question_type', 'points', 'answer_count')
    list_filter = ('exam', 'question_type')
    search_fields = ('text', 'exam__title')
    inlines = [ExamAnswerInline]

    def answer_count(self, obj):
        return obj.answers.count()
    answer_count.short_description = 'Answers'

@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('question', 'is_correct')
    search_fields = ('text', 'question__text')

@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'score', 'passed', 'completed', 'start_time', 'end_time')
    list_filter = ('exam', 'passed', 'completed', 'user', 'end_time')
    search_fields = ('user__username', 'exam__title',)
    readonly_fields = ('start_time', 'end_time')

@admin.register(ExamUserAnswer)
class ExamUserAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user', 'attempt', 'question', 'get_selected_answers', 'text_answer', 'is_correct')
    list_filter = ('is_correct', 'question__question_type')
    search_fields = ('attempt__user__username', 'question__text', 'text_answer')

    def get_selected_answers(self, obj):
        return ", ".join([a.text for a in obj.selected_answers.all()])
    get_selected_answers.short_description = "Selected Answers"

    def get_user(self, obj):
        return obj.attempt.user
    get_user.short_description = 'User'
    get_user.admin_order_field = 'attempt__user'
