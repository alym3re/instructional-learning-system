from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from django.core.mail import send_mail
from django.conf import settings

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    if created and instance.email:
        send_mail(
            'Welcome to Instructional Learning System',
            f'Hello {instance.first_name},\n\nWelcome to our platform! '
            f'Your student account ({instance.student_id}) has been successfully created.\n\n'
            'Start your learning journey now!',
            settings.DEFAULT_FROM_EMAIL,
            [instance.email],
            fail_silently=True,
        )