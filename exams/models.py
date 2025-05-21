from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

EXAM_GRADING_PERIOD_CHOICES = [
    ('prelim', 'Prelim'),
    ('midterm', 'Midterm'),
    ('prefinal', 'Prefinal'),
    ('final', 'Final'),
]

EXAM_QUESTION_TYPE_CHOICES = [
    ('multiple_choice', 'Multiple Choice'),
    ('true_false', 'True/False'),
    ('identification', 'Identification'),
    ('fill_in_the_blanks', 'Fill in the Blanks'),
]


class Exam(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes (0 for no limit)", default=0)
    passing_score = models.PositiveIntegerField(help_text="Percentage required to pass", default=70)
    locked = models.BooleanField(default=True, help_text="Lock this exam for non-admin users")
    shuffle_questions = models.BooleanField(default=False)
    show_correct_answers = models.BooleanField(help_text="Show correct answers after submission", default=True)
    grading_period = models.CharField(max_length=10, choices=EXAM_GRADING_PERIOD_CHOICES, default='prelim')
    lesson = models.ForeignKey('lessons.Lesson', on_delete=models.SET_NULL, related_name='exams', null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "exams"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['grading_period'], name='unique_exam_per_period')
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('exams:view_exam', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        # Enforce one exam per grading period
        if not self.pk and Exam.objects.filter(grading_period=self.grading_period).exists():
            raise ValueError('There can only be one exam per grading period.')
        if not self.slug:
            original_slug = slugify(self.title)
            slug = original_slug
            num = 1
            while Exam.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=["view_count"])

    def question_count(self):
        return self.questions.count()
        
    def get_ordered_questions(self):
        """
        Returns questions grouped by type in this order:
        1. Multiple Choice
        2. True/False
        3. Fill in the Blanks
        4. Identification
        """
        ORDER_MAP = {
            'multiple_choice': 0,
            'true_false': 1,
            'fill_in_the_blanks': 2,
            'identification': 3,
        }
        questions = list(self.questions.all())
        # Sort by question_type mapped by custom order
        return sorted(
            questions,
            key=lambda q: ORDER_MAP.get(q.question_type, 99)
        )

class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=EXAM_QUESTION_TYPE_CHOICES, default='multiple_choice')
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    
    class Meta:
        pass

    def __str__(self):
        label = dict(EXAM_QUESTION_TYPE_CHOICES).get(self.question_type, self.question_type)
        return f"[{label}] {self.text[:50]}..." if len(self.text) > 50 else f"[{label}] {self.text}"

    def is_multiple_choice(self):
        return self.question_type == 'multiple_choice'
    
    def is_true_false(self):
        return self.question_type == 'true_false'
    
    def is_identification(self):
        return self.question_type == 'identification'

    def is_fill_in_the_blanks(self):
        return self.question_type == 'fill_in_the_blanks'
        
    def blanks_count(self):
        """
        Returns the number of blanks for fill-in-the-blanks questions,
        based on the number of correct answers stored.
        """
        if not self.is_fill_in_the_blanks():
            return 0
        return self.answers.filter(is_correct=True).count()

    def total_points(self):
        """
        For fill-in-the-blanks, total points should be points multiplied by number of blanks.
        For other questions, it's self.points.
        """
        if self.is_fill_in_the_blanks():
            return self.points * self.blanks_count()
        return self.points
        
class ExamAnswer(models.Model):
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text[:50]}..." if len(self.text) > 50 else self.text

class ExamAttempt(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)  # percent out of 100
    raw_points = models.FloatField(null=True, blank=True)   # points earned
    total_points = models.FloatField(null=True, blank=True) # points possible
    passed = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    grading_period = models.CharField(
        max_length=10,
        choices=EXAM_GRADING_PERIOD_CHOICES,
        blank=True,
        null=True,
        help_text="Cached grading period for dashboard filtering"
    )

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.user.username} - {self.exam.title}"
        
    def save(self, *args, **kwargs):
        # Auto-set grading_period from the related exam
        if not self.grading_period and self.exam_id:
            try:
                self.grading_period = self.exam.grading_period
            except Exception:
                pass
        super().save(*args, **kwargs)

    def duration(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def duration_seconds(self):
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds())
        return None

    def duration_str(self):
        seconds = self.duration_seconds()
        if seconds is None:
            return "Not completed"
        minutes, sec = divmod(seconds, 60)
        if minutes and sec:
            return f"{minutes} minute{'s' if minutes != 1 else ''} {sec} second{'s' if sec != 1 else ''}"
        elif minutes:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif sec:
            return f"{sec} second{'s' if sec != 1 else ''}"
        else:
            return "0 seconds"

    def calculate_score(self):
        """
        Calculate score with per-blank points for fill_in_the_blanks questions.
        """
        gained_pts = 0
        total_pts = 0
        
        for q in self.exam.questions.all():
            if q.is_fill_in_the_blanks():
                # Per-blank calculation
                user_ans = self.user_answers.filter(question=q).first()
                blanks_count = q.blanks_count()
                per_blank_pts = q.points
                correct_blanks = user_ans.partial_score if user_ans else 0
                total_pts += per_blank_pts * blanks_count
                gained_pts += per_blank_pts * correct_blanks
            else:
                # Standard calculation for other question types
                total_pts += q.points
                if self.user_answers.filter(question=q, is_correct=True).exists():
                    gained_pts += q.points
                    
        self.raw_points = gained_pts
        self.total_points = total_pts
        self.score = (gained_pts / total_pts) * 100 if total_pts else 0
        self.passed = self.score >= self.exam.passing_score
        self.save()
        return self.score

class ExamUserAnswer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='exam_user_answers')
    selected_answers = models.ManyToManyField(ExamAnswer, blank=True, related_name='exam_user_selected_answers')
    text_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    partial_score = models.PositiveIntegerField(default=0, help_text="Number of correct blanks for fill-in-the-blanks questions")

    class Meta:
        unique_together = ('attempt', 'question')
        
    def check_answer(self):
        question = self.question
        if question.is_multiple_choice() or question.is_true_false():
            correct_answers = set(question.answers.filter(is_correct=True).values_list('id', flat=True))
            selected = set(self.selected_answers.values_list('id', flat=True))
            self.is_correct = correct_answers == selected
            self.partial_score = 1 if self.is_correct else 0
        elif question.is_identification():
            correct_answers = [a.text.lower().strip() for a in question.answers.filter(is_correct=True)]
            if self.text_answer:
                user_ans = self.text_answer.lower().strip()
                self.is_correct = user_ans in correct_answers
                self.partial_score = 1 if self.is_correct else 0
            else:
                self.is_correct = False
                self.partial_score = 0
        elif question.is_fill_in_the_blanks():
            correct_answers = [a.text.lower().strip() for a in question.answers.filter(is_correct=True)]
            if self.text_answer:
                user_blanks = [b.strip().lower() for b in self.text_answer.split('|')]
                # Partial credit: Each blank must match its correct answer
                correct_count = 0
                for idx, ca in enumerate(correct_answers):
                    # For out of bounds, can't be matched
                    if idx < len(user_blanks) and user_blanks[idx] == ca:
                        correct_count += 1
                self.partial_score = correct_count
                self.is_correct = (correct_count == len(correct_answers))
            else:
                self.is_correct = False
                self.partial_score = 0
        self.save()
        return self.is_correct
