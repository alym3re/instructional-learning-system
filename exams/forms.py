from django import forms
from .models import Exam, ExamQuestion, ExamAnswer, EXAM_QUESTION_TYPE_CHOICES

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            'title', 'description', 'grading_period', 'time_limit', 'passing_score', 'show_correct_answers'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'grading_period': forms.Select(attrs={'class': 'form-select'}),
            'time_limit': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'passing_score': forms.NumberInput(attrs={'min': 0, 'max': 100, 'class': 'form-control'}),
            'show_correct_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ExamQuestionForm(forms.ModelForm):
    # This will only be used for identification type
    correct_answer = forms.CharField(
        label="Correct Answer",
        max_length=500,
        required=False,  # Requiredness is validated in the view depending on type
        widget=forms.TextInput(attrs={'class': 'form-control input-identification'})
    )
    
    class Meta:
        model = ExamQuestion
        fields = ['text', 'question_type', 'explanation', 'points']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'explanation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        # For identification: If instance exists, set correct_answer field
        if instance and instance.question_type == 'identification':
            answer = instance.answers.filter(is_correct=True).first()
            if answer:
                self.fields['correct_answer'].initial = answer.text
        # If editing fill-in-the-blanks, store answers as a list (for display in JS)
        if instance and instance.question_type == 'fill_in_the_blanks':
            self.blank_answers_list = list(instance.answers.filter(is_correct=True).order_by('id').values_list('text', flat=True))
        else:
            self.blank_answers_list = []

class ExamAnswerForm(forms.ModelForm):
    class Meta:
        model = ExamAnswer
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ExamMultipleChoiceAnswerForm(ExamAnswerForm):
    """Form for multiple choice answers where only one answer can be correct"""
    pass

class ExamMultipleAnswerForm(ExamAnswerForm):
    """Form for multiple answer questions where multiple answers can be correct"""
    pass

class ExamTrueFalseAnswerForm(ExamAnswerForm):
    """Form specifically for True/False questions - always shows True and False options."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the text field: it should only be 'True' or 'False'
        self.fields['text'].widget = forms.HiddenInput()
        
    def clean(self):
        cleaned_data = super().clean()
        # Enforce only True or False as the text
        return cleaned_data

class ExamShortAnswerForm(ExamAnswerForm):
    """Form for short answer/identification questions"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_correct'].widget = forms.HiddenInput()
        self.fields['is_correct'].initial = True


class ExamFillInTheBlanksForm(ExamQuestionForm):
    # For FIB, "answers_list" will be posted as blank_answers[]
    answers_list = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ExamQuestion
        fields = ['text', 'question_type', 'explanation', 'points']
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Type your question and use [blank] for blanks e.g. "The capital of France is [blank]."'
            }),
            'question_type': forms.HiddenInput(),
            'explanation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'points': forms.NumberInput(attrs={
                'min': 1, 
                'class': 'form-control',
                'help_text': 'Points per blank'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.question_type == 'fill_in_the_blanks':
            # Pre-populate answers_list with existing blank answers
            answers = list(self.instance.answers.filter(is_correct=True).order_by('id').values_list('text', flat=True))
            self.initial['answers_list'] = ','.join(answers)

    def clean(self):
        cleaned = super().clean()
        text = cleaned.get('text', '')
        blanks_count = text.count('[blank]')

        # Get answers from either POST data or initial data (for editing)
        answers = self.data.getlist('blank_answers[]', [])
        if not answers and 'answers_list' in cleaned:
            # Handle comma-separated string if that's how it was submitted
            answers_value = cleaned['answers_list']
            if isinstance(answers_value, str) and ',' in answers_value:
                answers = answers_value.split(',')
            elif isinstance(answers_value, list):
                answers = answers_value
            else:
                answers = [answers_value] if answers_value else []
        
        if blanks_count != len(answers):
            raise forms.ValidationError("Number of blanks ([blank]) must match the number of answers provided.")
        
        cleaned['answers_list'] = answers
        return cleaned
from django.forms import inlineformset_factory

ExamAnswerFormSet = inlineformset_factory(
    ExamQuestion, ExamAnswer, form=ExamAnswerForm, extra=2, can_delete=True, min_num=2
)

ExamMultipleChoiceFormSet = forms.inlineformset_factory(
    ExamQuestion, ExamAnswer, form=ExamMultipleChoiceAnswerForm, extra=4, can_delete=True, min_num=2, max_num=4
)

ExamMultipleAnswerFormSet = forms.inlineformset_factory(
    ExamQuestion, ExamAnswer, form=ExamMultipleAnswerForm, extra=4, can_delete=True, min_num=2, max_num=4
)

# For true/false: always make two forms, one for 'True', one for 'False'
ExamTrueFalseFormSet = forms.inlineformset_factory(
    ExamQuestion, ExamAnswer, form=ExamTrueFalseAnswerForm, extra=2, can_delete=False, min_num=2, max_num=2
)

ExamShortAnswerFormSet = forms.inlineformset_factory(
    ExamQuestion, ExamAnswer, form=ExamShortAnswerForm, extra=1, can_delete=True, min_num=1, max_num=1
)


def get_answer_formset_for_question_type(question_type):
    formset_map = {
        'multiple_choice': ExamMultipleChoiceFormSet,
        'multiple_answer': ExamMultipleAnswerFormSet,
        'true_false': ExamTrueFalseFormSet,
        'short_answer': ExamShortAnswerFormSet,
        'identification': ExamShortAnswerFormSet,
        'fill_in_the_blanks': None,
    }
    return formset_map.get(question_type, ExamAnswerFormSet)
