from django.db import models
from django.contrib.auth import get_user_model
from lessons.models import Lesson
from quizzes.models import QuizAttempt, Quiz
from exams.models import ExamAttempt

from django.db.models import JSONField

class StudentProgress(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='progress')
    last_active = models.DateTimeField(auto_now=True)
    custom_fields = JSONField(default=dict, blank=True)  # For admin-added columns

    def __str__(self):
        return f"{self.user.username}'s Progress"


class ActivityLog(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50, choices=[
        ('lesson', 'Lesson Completed'),
        ('quiz', 'Quiz Taken'),
        ('exam', 'Exam Taken'),
        ('login', 'Login'),
        ('achievement', 'Achievement Unlocked')
    ])
    object_id = models.PositiveIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"


from lessons.models import GRADING_PERIOD_CHOICES

class Attendance(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    grading_period = models.CharField(max_length=10, choices=GRADING_PERIOD_CHOICES, default='prelim')
    total_days = models.PositiveIntegerField(default=0)
    days_present = models.PositiveIntegerField(default=0)
    remarks = models.CharField(max_length=255, blank=True)

    @property
    def percent(self):
        if self.total_days:
            return round((self.days_present / self.total_days) * 100, 2)
        return 0.0

    class Meta:
        unique_together = ('user', 'grading_period')
        ordering = ['user']

    def __str__(self):
        return f"{self.user.username} - Present: {self.days_present}/{self.total_days}"