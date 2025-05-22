from django import forms
from .models import Quiz, Question, Answer, QUESTION_TYPE_CHOICES


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
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

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'explanation', 'points']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'explanation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
        }

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MultipleChoiceAnswerForm(AnswerForm):
    """Form for multiple choice answers where only one answer can be correct"""
    pass

class MultipleAnswerForm(AnswerForm):
    """Form for multiple answer questions where multiple answers can be correct"""
    pass

class TrueFalseAnswerForm(AnswerForm):
    """Form specifically for True/False questions"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget = forms.Select(
            choices=[('True', 'True'), ('False', 'False')],
            attrs={'class': 'form-select'}
        )

class ShortAnswerForm(AnswerForm):
    """Form for short answer questions"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_correct'].widget = forms.HiddenInput()
        self.fields['is_correct'].initial = True

class FillInTheBlanksForm(forms.ModelForm):
    """Form for fill-in-the-blanks questions: support dynamic blank answers as blank_answers[] on POST"""

    class Meta:
        model = Question
        fields = ['text', 'question_type', 'explanation', 'points']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'explanation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.blank_answers = []
        if self.is_bound:
            self.blank_answers = self.data.getlist('blank_answers[]') if hasattr(self.data, 'getlist') else []
    
    def clean(self):
        cleaned_data = super().clean()
        if self.blank_answers:
            cleaned_blanks = [b.strip() for b in self.blank_answers if b.strip()]
            text = cleaned_data.get('text', '')
            blanks_count = text.count('[blank]')
            if blanks_count != len(cleaned_blanks):
                raise forms.ValidationError(f"Number of blank answers ({len(cleaned_blanks)}) must match number of [blank] in question ({blanks_count}).")
            if any(not ans for ans in cleaned_blanks):
                raise forms.ValidationError("All blank answers are required for fill-in-the-blanks questions.")
            cleaned_data['blank_answers'] = cleaned_blanks
        else:
            raise forms.ValidationError("You must provide blank answers for fill-in-the-blanks questions.")
        return cleaned_data

# Base formset for answers
AnswerFormSet = forms.inlineformset_factory(
    Question, Answer, form=AnswerForm, extra=2, can_delete=True, min_num=2
)

# Specialized formsets for different question types
MultipleChoiceFormSet = forms.inlineformset_factory(
    Question, Answer, form=MultipleChoiceAnswerForm, extra=4, can_delete=True, min_num=2
)

MultipleAnswerFormSet = forms.inlineformset_factory(
    Question, Answer, form=MultipleAnswerForm, extra=4, can_delete=True, min_num=2
)

TrueFalseFormSet = forms.inlineformset_factory(
    Question, Answer, form=TrueFalseAnswerForm, extra=2, can_delete=True, min_num=2, max_num=2
)

ShortAnswerFormSet = forms.inlineformset_factory(
    Question, Answer, form=ShortAnswerForm, extra=1, can_delete=True, min_num=1, max_num=1
)

FillInTheBlanksFormSet = forms.inlineformset_factory(
    Question, Answer, form=AnswerForm, extra=0, can_delete=True, min_num=0
)

# Factory function to get the appropriate formset based on question type
def get_answer_formset_for_question_type(question_type):
    formset_map = {
        'multiple_choice': MultipleChoiceFormSet,
        'multiple_answer': MultipleAnswerFormSet,
        'true_false': TrueFalseFormSet,
        'short_answer': ShortAnswerFormSet,
        'fill_in_the_blanks': FillInTheBlanksFormSet,
    }
    return formset_map.get(question_type, AnswerFormSet)
