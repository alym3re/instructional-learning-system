import random
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.forms import inlineformset_factory
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.views.decorators.http import require_POST
from .models import Exam, ExamQuestion, ExamAnswer, ExamAttempt, ExamUserAnswer, EXAM_GRADING_PERIOD_CHOICES, EXAM_QUESTION_TYPE_CHOICES
from .utils import safe_count
from .forms import ExamForm, ExamQuestionForm, ExamAnswerForm, ExamAnswerFormSet, ExamMultipleChoiceFormSet, ExamTrueFalseFormSet, ExamFillInTheBlanksForm
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required


# Utility function to get the *real* points of an exam (per-blank for fill_in_the_blanks)
def get_exam_overall_points(questions):
    total = 0
    for q in questions:
        if q.question_type == 'fill_in_the_blanks':
            total += q.answers.filter(is_correct=True).count()
        else:
            total += q.points
    return total



def grading_period_exam_list(request):
    periods = EXAM_GRADING_PERIOD_CHOICES
    period_stats = {}
    user = request.user if request.user.is_authenticated else None

    def get_exam_overall_points_v2(questions):
        total = 0
        for q in questions:
            # Count FIB total as blanks count * question points
            if hasattr(q, "is_fill_in_the_blanks") and q.is_fill_in_the_blanks():
                total += q.points * q.blanks_count()
            else:
                total += q.points
        return total

    for period_value, period_label in periods:
        try:
            exam = Exam.objects.get(grading_period=period_value)
            questions = exam.get_ordered_questions() if hasattr(exam, "get_ordered_questions") else exam.questions.all()
            questions_count = safe_count(questions)
            # Use improved scoring
            overall_score = get_exam_overall_points_v2(questions) if questions else 0
            passing_score = int((exam.passing_score / 100) * overall_score) if overall_score > 0 else 0
            passing_percent = exam.passing_score if exam else 0
            view_count = exam.view_count or 0
            completed = False
            exam_attempt = None
            if user:
                exam_attempt = ExamAttempt.objects.filter(user=user, exam=exam, completed=True).order_by('-end_time').first()
                completed = bool(exam_attempt)
            exam_count = 1
        except Exam.DoesNotExist:
            exam = None
            exam_count = 0
            view_count = 0
            questions = []
            questions_count = 0
            overall_score = 0
            passing_score = 0
            passing_percent = 0
            completed = False
            exam_attempt = None

        period_stats[period_value] = {
            "label": period_label,
            "exam_count": exam_count,
            "view_count": view_count,
            "questions_count": questions_count,
            "completed": completed,
            "exams": [exam] if exam else [],
            "exam": exam,
            "attempt_for_user": exam_attempt,
            "overall_score": overall_score,
            "passing_score": passing_score,
            "passing_percent": passing_percent,
            # DO NOT include FIB note!
        }

    context = {
        "periods": periods,
        "period_stats": period_stats,
        "is_admin": user.is_staff if user else False,
    }
    return render(request, "exams/grading_period_exam_list.html", context)


@login_required
def create_exam(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to create exams.")
        return redirect('exams:grading_period_exam_list')

    # Get grading_period from GET parameter or POST (fallback)
    grading_period = (
        request.GET.get('grading_period')
        or request.POST.get('grading_period')
        or None
    )

    # Resolve grading period label
    grading_period_label = None
    if grading_period:
        grading_period_label = dict(EXAM_GRADING_PERIOD_CHOICES).get(grading_period, grading_period.title())
    else:
        grading_period_label = None

    if request.method == 'POST':
        post_data = request.POST.copy()

        # If title and grading_period are missing in POST, set them explicitly
        if grading_period_label and not post_data.get('title'):
            post_data['title'] = f"{grading_period_label} Exam"
        if grading_period and not post_data.get('grading_period'):
            post_data['grading_period'] = grading_period

        form = ExamForm(post_data, request.FILES)
        if form.is_valid():
            try:
                exam = form.save(commit=False)
                exam.created_by = request.user
                exam.save()
                messages.success(request, 'Exam created successfully!')
                return redirect('exams:add_exam_questions', exam_id=exam.id)
            except Exception as e:
                form.add_error(None, str(e))
    else:
        # Set initial data for form when GET
        initial = {}
        if grading_period_label:
            initial['title'] = f"{grading_period_label} Exam"
        if grading_period:
            initial['grading_period'] = grading_period
        form = ExamForm(initial=initial)

    return render(request, 'exams/create.html', {
        'form': form,
        'grading_period': grading_period,
        'grading_period_label': grading_period_label,
    })


def exam_by_period(request, grading_period):
    valid_periods = [c[0] for c in EXAM_GRADING_PERIOD_CHOICES]
    if grading_period not in valid_periods:
        messages.error(request, "Invalid grading period.")
        return redirect('exams:grading_period_exam_list')

    try:
        exam = Exam.objects.get(grading_period=grading_period)
    except Exam.DoesNotExist:
        exam = None

    context = {
        'grading_period': grading_period,
        'grading_period_display': dict(EXAM_GRADING_PERIOD_CHOICES)[grading_period],
        'exam': exam,
        'user': request.user,
    }
    return render(request, "exams/by_period.html", context)

@login_required
def exam_list(request):
    return redirect('exams:grading_period_exam_list')

@login_required
def view_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if hasattr(exam, 'increment_view_count'):
        exam.increment_view_count()
    questions = exam.get_ordered_questions()
    
    # Calculate overall score and passing points
    overall_score = get_exam_overall_points(questions)
    passing_points = int((exam.passing_score / 100) * overall_score)
    
    completed = False
    attempt = None
    if request.user.is_authenticated:
        attempt = ExamAttempt.objects.filter(user=request.user, exam=exam).first()
        completed = attempt.completed if attempt else False
    
    context = {
        'exam': exam,
        'questions': questions,
        'completed': completed,
        'user_attempt': attempt,
        'overall_score': overall_score,
        'passing_points': passing_points,
        'passing_percent': exam.passing_score,
    }
    if exam.locked and not request.user.is_staff:
        messages.error(request, "This exam is locked.")
        return redirect('exams:grading_period_exam_list')
    return render(request, "exams/view.html", context)

def get_answer_formset_for_question_type(question_type):
    """Return the appropriate formset based on question type"""
    if question_type == 'multiple_choice':
        return ExamMultipleChoiceFormSet
    elif question_type == 'true_false':
        return ExamTrueFalseFormSet
    elif question_type in ['identification', 'fill_in_the_blanks']:
        return None
    else:
        return ExamAnswerFormSet

@login_required
def add_exam_questions(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff or exam.created_by != request.user:
        messages.error(request, "You don't have permission to edit this exam.")
        return redirect('exams:exam_by_period', grading_period=exam.grading_period)

    default_question_type = 'multiple_choice'
    error_message = None

    if request.method == 'POST':
        qtype = request.POST.get('question_type', default_question_type)
        if qtype == 'fill_in_the_blanks':
            question_form = ExamFillInTheBlanksForm(request.POST)
            answer_formset = None
        elif qtype == 'identification':
            question_form = ExamQuestionForm(request.POST)
            answer_formset = None  # skip formset; we handle manually
        else:
            question_form = ExamQuestionForm(request.POST)
            AnswerFormSet = get_answer_formset_for_question_type(qtype)
            answer_formset = AnswerFormSet(request.POST, prefix='answers') if AnswerFormSet else None

        # Validation & saving logic
        valid = question_form.is_valid() and (answer_formset is None or answer_formset.is_valid())
        # For identification, ensure correct_answer exists
        if qtype == 'identification' and not request.POST.get('correct_answer', '').strip():
            valid = False
            error_message = "Correct answer is required for identification question."

        if valid:
            with transaction.atomic():
                question = question_form.save(commit=False)
                question.exam = exam
                question.save()

                # Force question_type (in case select is fiddled with)
                question.question_type = qtype
                
                if qtype == 'fill_in_the_blanks':
                    # Save each blank as an ExamAnswer
                    answers_list = question_form.cleaned_data['answers_list']
                    for blank_answer in answers_list:
                        ExamAnswer.objects.create(
                            question=question,
                            text=blank_answer.strip(),
                            is_correct=True
                        )
                elif qtype == 'identification':
                    answer_text = request.POST.get('correct_answer', '').strip()
                    ExamAnswer.objects.create(
                        question=question,
                        text=answer_text,
                        is_correct=True
                    )
                elif qtype == 'true_false':
                    # Ensure exactly two ExamAnswer options: True and False
                    if answer_formset is not None:
                        answers = answer_formset.save(commit=False)
                        # Delete any existing answers first
                        ExamAnswer.objects.filter(question=question).delete()
                        # Create True and False options
                        for idx, answer in enumerate(answers):
                            answer.question = question
                            answer.text = 'True' if idx == 0 else 'False'
                            answer.save()
                else:
                    # For multiple choice and other types
                    if answer_formset is not None:
                        answers = answer_formset.save(commit=False)
                        for answer in answers:
                            answer.question = question
                            answer.save()
                        answer_formset.save_m2m()
                        
                messages.success(request, 'Question added successfully!')
                return redirect('exams:add_exam_questions', exam_id=exam.id)
        else:
            error_message = "Invalid question or answer form"
    else:
        qtype = request.GET.get('question_type', default_question_type)
        if qtype == 'fill_in_the_blanks':
            question_form = ExamFillInTheBlanksForm(initial={'question_type': 'fill_in_the_blanks'})
            answer_formset = None
        elif qtype == 'identification':
            question_form = ExamQuestionForm(initial={'question_type': 'identification'})
            answer_formset = None
        else:
            question_form = ExamQuestionForm(initial={'question_type': qtype})
            AnswerFormSet = get_answer_formset_for_question_type(qtype)
            
            if qtype == 'true_false' and AnswerFormSet:
                # Pre-fill with "True" and "False"
                answer_formset = AnswerFormSet(
                    prefix='answers',
                    initial=[
                        {'text': 'True', 'is_correct': False},
                        {'text': 'False', 'is_correct': False}
                    ]
                )
            else:
                answer_formset = AnswerFormSet(prefix='answers') if AnswerFormSet else None

    questions = exam.get_ordered_questions()
    return render(request, 'exams/add_questions.html', {
        'exam': exam,
        'question_form': question_form,
        'answer_formset': answer_formset,
        'questions': questions,
        'error': error_message,
    })


@login_required
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    user_attempt = ExamAttempt.objects.filter(user=request.user, exam=exam).first()
    if user_attempt and user_attempt.completed:
        messages.info(request, "You have already completed this exam. You cannot take it again.")
        return redirect('exams:view_exam', exam_id=exam.id)
    elif user_attempt is None:
        user_attempt = ExamAttempt.objects.create(user=request.user, exam=exam)

    if exam.locked and not request.user.is_staff:
        messages.error(request, "This exam is locked.")
        return redirect('exams:grading_period_exam_list')
    
    # Calculate overall score and passing points
    questions = exam.get_ordered_questions()
    overall_score = get_exam_overall_points(questions)
    passing_points = int((exam.passing_score / 100) * overall_score)

    if request.method == 'POST':
        with transaction.atomic():
            total_points = 0
            total_score = 0

            for question in exam.get_ordered_questions():
                question_type = question.question_type
                user_answer_obj, _ = ExamUserAnswer.objects.get_or_create(attempt=user_attempt, question=question)
                user_answer_obj.is_correct = False

                if question_type.startswith('multiple'):
                    choice_ids = request.POST.getlist(f'question_{question.id}')
                    selected_answers = ExamAnswer.objects.filter(question=question, id__in=choice_ids)
                    user_answer_obj.selected_answers.set(selected_answers)
                elif question_type == 'true_false':
                    choice_id = request.POST.get(f'question_{question.id}')
                    if choice_id:
                        answer = ExamAnswer.objects.filter(question=question, id=choice_id).first()
                        if answer:
                            user_answer_obj.selected_answers.set([answer])
                elif question_type == 'identification':
                    text_ans = request.POST.get(f'question_{question.id}_text', '').strip()
                    user_answer_obj.text_answer = text_ans
                elif question_type == 'fill_in_the_blanks':
                    blanks = request.POST.getlist(f'question_{question.id}_blank[]')
                    user_answer_obj.text_answer = '|'.join([b.strip() for b in blanks])
                
                # Calculate per-blank score for fill_in_the_blanks questions
                if question_type == 'fill_in_the_blanks':
                    correct_blanks = question.answers.filter(is_correct=True).values_list('text', flat=True)
                    user_blanks = [b.strip().lower() for b in blanks]
                    n_blanks = len(correct_blanks)
                    per_blank_pts = question.points
                    
                    # Count correct answers
                    correct_count = 0
                    for i, correct_answer in enumerate(correct_blanks):
                        if i < len(user_blanks) and user_blanks[i].lower() == correct_answer.lower():
                            correct_count += 1
                    
                    # Store partial score information
                    user_answer_obj.partial_score = correct_count
                    user_answer_obj.is_correct = correct_count == n_blanks
                    
                    # Add to totals - multiply by points per blank
                    total_points += per_blank_pts * n_blanks
                    total_score += per_blank_pts * correct_count
                else:
                    user_answer_obj.check_answer()
                    total_points += question.points
                    if user_answer_obj.is_correct:
                        total_score += question.points
                
                user_answer_obj.save()

            exam_score = (total_score / total_points) * 100 if total_points > 0 else 0
            user_attempt.raw_points = total_score
            user_attempt.total_points = total_points
            user_attempt.score = exam_score
            user_attempt.completed = True
            user_attempt.passed = exam_score >= exam.passing_score
            user_attempt.end_time = timezone.now()
            user_attempt.save()
            messages.success(request, f"Exam submitted! Your score: {user_attempt.raw_points}/{user_attempt.total_points} points ({user_attempt.score:.2f}%)")
            return redirect('exams:exam_results', attempt_id=user_attempt.id)

    questions = exam.get_ordered_questions()
    return render(request, 'exams/take.html', {
        'exam': exam,
        'questions': questions,
        'user_attempt': user_attempt,
        'overall_score': overall_score,
        'passing_points': passing_points,
        'passing_percent': exam.passing_score,
    })

@login_required
def exam_results(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, user=request.user)
    exam = attempt.exam
    user_answers = attempt.user_answers.select_related('question').prefetch_related('selected_answers')
    return render(request, 'exams/results.html', {
        'exam': exam,
        'attempt': attempt,
        'user_answers': user_answers
    })

@login_required
def exam_history(request):
    attempts_qs = ExamAttempt.objects.filter(user=request.user).select_related('exam').order_by('-start_time')
    paginator = Paginator(attempts_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'exams/history.html', {'page_obj': page_obj})

@login_required
def archive_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:view_exam', exam_id=exam_id)
    messages.success(request, "Exam archived.")
    return redirect('exams:grading_period_exam_list')

@login_required
def unarchive_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:view_exam', exam_id=exam_id)
    messages.success(request, "Exam unarchived.")
    return redirect('exams:grading_period_exam_list')

@login_required
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:view_exam', exam_id=exam_id)
    
    if request.method == 'POST':
        form = ExamForm(request.POST, request.FILES, instance=exam)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Exam updated successfully.")
                return redirect('exams:view_exam', exam_id=exam.id)
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ExamForm(instance=exam)
    return render(request, 'exams/edit.html', {'form': form, 'exam': exam})

@login_required
def delete_exam_question(request, exam_id, question_id):
    exam = get_object_or_404(Exam, id=exam_id)
    question = get_object_or_404(ExamQuestion, id=question_id, exam=exam)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:add_exam_questions', exam_id=exam.id)
    question.delete()
    messages.success(request, "Question deleted.")
    return redirect('exams:add_exam_questions', exam_id=exam.id)

@login_required
def lock_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:view_exam', exam_id=exam_id)
    exam.locked = True
    exam.save(update_fields=['locked'])
    messages.success(request, "Exam locked.")
    return redirect('exams:view_exam', exam_id=exam_id)

@login_required
def unlock_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('exams:view_exam', exam_id=exam_id)
    exam.locked = False
    exam.save(update_fields=['locked'])
    messages.success(request, "Exam unlocked.")
    return redirect('exams:view_exam', exam_id=exam_id)

@staff_member_required  # from django.contrib.admin.views.decorators!
def toggle_period_lock(request, grading_period):
    exam = Exam.objects.filter(grading_period=grading_period).first()
    if exam:
        exam.locked = not exam.locked
        exam.save(update_fields=['locked'])
        if exam.locked:
            messages.success(request, f"{dict(EXAM_GRADING_PERIOD_CHOICES).get(grading_period, grading_period)} exam locked.")
        else:
            messages.success(request, f"{dict(EXAM_GRADING_PERIOD_CHOICES).get(grading_period, grading_period)} exam unlocked.")
    else:
        messages.error(request, "No exam for this grading period.")
    return HttpResponseRedirect(reverse('exams:grading_period_exam_list'))
