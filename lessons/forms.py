from django import forms
from .models import Lesson, GRADING_PERIOD_CHOICES

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'description', 'grading_period', 'file', ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'grading_period': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.ms-powerpoint'
            }),
        }
        labels = {
            'description': 'Description',        }
        help_texts = {
            'file': 'Only .pdf, .doc, .docx files are allowed.',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        allowed_exts = ['.pdf', '.doc', '.docx', '.pptx']
        import os
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_exts:
            raise forms.ValidationError("Only PDF and Word (.doc/.docx) files are allowed.")
        return file