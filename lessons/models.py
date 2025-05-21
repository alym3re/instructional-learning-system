from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

GRADING_PERIOD_CHOICES = [
    ('prelim', 'Prelim'),
    ('midterm', 'Midterm'),
    ('prefinal', 'Prefinal'),
    ('final', 'Final'),
]

def lesson_file_path(instance, filename):
    return f'lesson_files/lesson_{instance.id}/{filename}'

class Lesson(models.Model):
    grading_period = models.CharField(
        max_length=10, 
        choices=GRADING_PERIOD_CHOICES,
        default='prelim'
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(help_text="Lesson description")
    file = models.FileField(upload_to=lesson_file_path)
    thumbnail = models.ImageField(upload_to='lesson_thumbnails/', blank=True, null=True)
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    upload_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)

    is_archived = models.BooleanField(default=False)  # New field for archiving
    # Optional: field for HTML-converted doc/docx. Needs backend job to populate!
    html_content = models.TextField(blank=True, null=True, help_text="Auto-generated HTML from .docx if available")

    class Meta:
        ordering = ['-upload_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        try:
            # Only clear html_content if this is NOT a new object and file has changed
            old = self.__class__.objects.get(pk=self.pk)
            old_file = old.file
        except (self.__class__.DoesNotExist, ValueError, TypeError):
            old_file = None

        # If the file field has changed (and it's not a new object), reset html_content
        if old_file and old_file.name != self.file.name:
            self.html_content = ''

        if not self.slug or self.__class__.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            original_slug = slugify(self.title)
            slug = original_slug
            num = 1
            while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{original_slug}-{num}"
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def extension(self):
        import os
        name, extension = os.path.splitext(self.file.name)
        return extension.lower()

    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=["view_count"])

class LessonAccess(models.Model):
    ACCESS_TYPE_CHOICES = [
        ('view', 'Viewed'),
        ('download', 'Downloaded'),
    ]
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    grading_period = models.CharField(
        max_length=10,
        choices=GRADING_PERIOD_CHOICES,
        blank=True,
        null=True,
        help_text="Cached grading period for filtering dashboard views"
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} {self.access_type} {self.lesson.title} on {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Auto-set grading_period from the associated lesson
        if not self.grading_period and self.lesson:
            self.grading_period = self.lesson.grading_period
        super().save(*args, **kwargs)

class LessonProgress(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    last_viewed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'lesson')
        verbose_name_plural = "Lesson Progress"

    def __str__(self):
        return f"{self.user.username} - {self.lesson.title}"

class PeriodLock(models.Model):
    grading_period = models.CharField(
        max_length=10,
        choices=GRADING_PERIOD_CHOICES,
        unique=True
    )
    locked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_grading_period_display()} ({'Locked' if self.locked else 'Unlocked'})"
