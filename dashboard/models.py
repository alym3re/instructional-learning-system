from django.db import models
from django.contrib.auth import get_user_model
from lessons.models import Lesson
from quizzes.models import QuizAttempt, Quiz
from exams.models import ExamAttempt

class StudentProgress(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='progress')
    last_active = models.DateTimeField(auto_now=True)
    total_xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    badges = models.ManyToManyField('Badge', blank=True)

    def __str__(self):
        return f"{self.user.username}'s Progress"

    def calculate_level(self):
        # Simple level calculation (1000 XP per level)
        self.level = self.total_xp // 1000 + 1
        self.save()
        return self.level

class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    xp_reward = models.IntegerField(default=100)
    condition = models.CharField(max_length=200, help_text="Condition to earn this badge")

    def __str__(self):
        return self.name

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
    xp_earned = models.IntegerField(default=0)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"


class Attendance(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    total_days = models.PositiveIntegerField(default=0)
    days_present = models.PositiveIntegerField(default=0)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('user',)
        ordering = ['user']

    def __str__(self):
        return f"{self.user.username} - Present: {self.days_present}/{self.total_days}"