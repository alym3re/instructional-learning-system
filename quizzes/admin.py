
from django.contrib import admin
from .models import Quiz, Question, Answer, QuizAttempt, UserAnswer

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    min_num = 2

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'grading_period', 'created_by', 'created_at', 'is_archived', 'question_count'
    )
    list_filter = ('is_archived', 'grading_period', 'created_at')
    search_fields = ('title', 'description', 'created_by__username')
    inlines = [QuestionInline]
    readonly_fields = ('view_count', 'created_at', 'updated_at')

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'question_type', 'points', 'order', 'answer_count')
    list_filter = ('quiz', 'question_type')
    search_fields = ('text', 'quiz__title')
    inlines = [AnswerInline]

    def answer_count(self, obj):
        return obj.answers.count()
    answer_count.short_description = 'Answers'

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('question', 'is_correct')
    search_fields = ('text', 'question__text')

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'passed', 'completed', 'start_time', 'end_time')
    list_filter = ('quiz', 'passed', 'completed', 'user', 'end_time')
    search_fields = ('user__username', 'quiz__title',)
    readonly_fields = ('start_time', 'end_time')

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user', 'attempt', 'question', 'get_selected_answers', 'text_answer', 'is_correct')
    list_filter = ('is_correct', 'question__question_type')
    search_fields = ('attempt__user__username', 'question__text', 'text_answer')

    def get_selected_answers(self, obj):
        # For multiple choice: display selected answers
        return ", ".join([a.text for a in obj.selected_answers.all()])
    get_selected_answers.short_description = "Selected Answers"

    def get_user(self, obj):
        return obj.attempt.user
    get_user.short_description = 'User'
    get_user.admin_order_field = 'attempt__user'
