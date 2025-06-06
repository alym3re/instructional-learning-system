import random
import json
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
    
    # Pass all user attempts for staff to display full leaderboard
    user_attempts = None
    if request.user.is_staff:
        user_attempts = ExamAttempt.objects.filter(exam=exam, completed=True).select_related('user').order_by('-score', '-end_time')
    else:
        # Only their own attempt for students (could be empty query)
        user_attempts = ExamAttempt.objects.filter(exam=exam, user=request.user)
    
    # Try to build section choices from user_attempts (populate with distinct values)
    user_sections = set()
    section_labels = {}
    for ua in user_attempts:
        # For safety: handle users with/without section value
        section_val = getattr(ua.user, "section", None)
        if section_val is not None and section_val != "":
            user_sections.add(section_val)
            # If User model has a get_section_display(), use it; else use the raw value
            label = (
                ua.user.get_section_display()
                if hasattr(ua.user, "get_section_display") else section_val
            )
            section_labels[section_val] = label

    # Create a sorted list of (section, label)
    section_choices = sorted(
        [(sec, section_labels[sec]) for sec in user_sections],
        key=lambda x: x[1]
    )
    
    context = {
        'exam': exam,
        'questions': questions,
        'completed': completed,
        'user_attempt': attempt,
        'overall_score': overall_score,
        'passing_points': passing_points,
        'passing_percent': exam.passing_score,
        'user_attempts': user_attempts,  # For results modal/leaderboard
        'section_choices': section_choices,  # For filtering attempts by section
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

    questions = exam.get_ordered_questions()
    default_question_type = 'multiple_choice'
    error_message = None

    # Handle edit mode: GET param preferred for idempotency
    edit_question_id = request.GET.get("edit_question_id") or request.POST.get("edit_question_id") or ""
    edit_mode = bool(edit_question_id)
    instance = None

    # Cancel edit mode
    if request.method == "POST" and request.POST.get("cancel_edit") == "1":
        return redirect('exams:add_exam_questions', exam_id=exam.id)

    # On GET - load question instance, prepopulate forms/fields
    if edit_mode:
        try:
            instance = exam.questions.get(id=edit_question_id)
            default_question_type = instance.question_type
        except Exception:
            instance = None
            edit_mode = False

    # Get the right form and answer formset for question type
    qtype = request.POST.get('question_type') or request.GET.get('question_type') or default_question_type

    if request.method == 'POST':
        # Use right form for type and editing instance if set
        if qtype == 'fill_in_the_blanks':
            question_form = ExamFillInTheBlanksForm(request.POST, instance=instance)
            answer_formset = None
        elif qtype == 'identification':
            question_form = ExamQuestionForm(request.POST, instance=instance)
            answer_formset = None
            # Manually add correct_answer to form data if it exists
            if 'correct_answer' in request.POST:
                question_form.data = question_form.data.copy()
                question_form.data['correct_answer'] = request.POST['correct_answer']
        else:
            question_form = ExamQuestionForm(request.POST, instance=instance)
            AnswerFormSet = get_answer_formset_for_question_type(qtype)
            answer_formset = AnswerFormSet(request.POST, prefix='answers') if AnswerFormSet else None

        valid = question_form.is_valid() and (answer_formset is None or answer_formset.is_valid())
        if qtype == 'identification' and not request.POST.get('correct_answer', '').strip():
            valid = False
            error_message = "Correct answer is required for identification question."

        if valid:
            with transaction.atomic():
                question = question_form.save(commit=False)
                question.exam = exam
                question.question_type = qtype
                question.save()

                # Remove old answers if editing
                if edit_mode and instance:
                    ExamAnswer.objects.filter(question=question).delete()
                
                if qtype == 'fill_in_the_blanks':
                    # Save each blank as an ExamAnswer
                    answers_list = question_form.cleaned_data.get('answers_list', [])
                    for blank_answer in answers_list:
                        ExamAnswer.objects.create(
                            question=question,
                            text=blank_answer.strip(),
                            is_correct=True
                        )
                elif qtype == 'identification':
                    answer_text = request.POST.get('correct_answer', '').strip()
                    if answer_text:  # Only create if answer exists
                        ExamAnswer.objects.create(
                            question=question,
                            text=answer_text,
                            is_correct=True
                        )
                elif qtype == 'true_false':
                    # Ensure exactly two ExamAnswer options: True and False
                    if answer_formset is not None:
                        answers = answer_formset.save(commit=False)
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
                
                messages.success(request, 'Question {} successfully!'.format('updated' if edit_mode else 'added'))
                return redirect('exams:add_exam_questions', exam_id=exam.id)
        else:
            error_message = "Invalid question or answer form"
    
    else:  # GET request
        # GET: set up forms with instance OR blank with defaults
        if edit_mode and instance:
            qtype = instance.question_type
            if qtype == 'fill_in_the_blanks':
                question_form = ExamFillInTheBlanksForm(instance=instance)
                # The form will handle populating answers_list via its __init__
                answer_formset = None
            elif qtype == 'identification':
                question_form = ExamQuestionForm(instance=instance)
                # Get the correct answer and add it to initial data
                correct_answer = instance.answers.filter(is_correct=True).first()
                if correct_answer:
                    question_form.initial['correct_answer'] = correct_answer.text
                answer_formset = None
            else:
                question_form = ExamQuestionForm(instance=instance)
                AnswerFormSet = get_answer_formset_for_question_type(qtype)
                answers = list(ExamAnswer.objects.filter(question=instance).order_by('id'))
                # Ensure initial reflects db and shows correct checked state
                answer_formset = AnswerFormSet(
                    queryset=ExamAnswer.objects.filter(question=instance),
                    prefix='answers',
                    initial=[
                        {'text': ans.text, 'is_correct': ans.is_correct} for ans in answers
                    ]
                ) if AnswerFormSet else None
        else:
            # Not editing: blank/default forms
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

    context = {
        'exam': exam,
        'question_form': question_form,
        'answer_formset': answer_formset,
        'questions': questions,
        'error': error_message,
        'edit_mode': edit_mode,
        'edit_question_id': edit_question_id if edit_mode else '',
        'question_type': qtype,
    }
    
    # Process blank answers for fill_in_the_blanks questions
    blank_answers = []
    if qtype == 'fill_in_the_blanks':
        if edit_mode and instance:
            # Get all blank answers in order for existing question
            blank_answers = list(instance.answers.filter(is_correct=True).order_by('id').values_list('text', flat=True))
        elif hasattr(question_form, 'cleaned_data'):
            # After POST
            blank_answers = question_form.cleaned_data.get('answers_list', [])
        elif hasattr(question_form, 'initial'):
            # After GET with initial data
            answers_str = question_form.initial.get('answers_list', '')
            if isinstance(answers_str, str):
                blank_answers = [a.strip() for a in answers_str.split(',') if a.strip()]
    
    # Get identification answer if needed
    ident_answer = ''
    if qtype == 'identification' and edit_mode and instance:
        ident_answer_obj = instance.answers.filter(is_correct=True).first()
        ident_answer = ident_answer_obj.text if ident_answer_obj else ''
    
    # Add additional context for edit mode to properly populate form fields
    context = {
        'exam': exam,
        'question_form': question_form,
        'answer_formset': answer_formset,
        'questions': questions,
        'error': error_message,
        'edit_mode': edit_mode,
        'edit_question_id': edit_question_id if edit_mode else '',
        'question_type': qtype,
        'blank_answers': blank_answers,
        'blank_answers_json': json.dumps(blank_answers),  # Always valid JS array
        'ident_answer': ident_answer,
    }
    
    # Provide question_to_edit for template logic
    if edit_mode and instance:
        context['question_to_edit'] = instance
    
    return render(request, 'exams/add_questions.html', context)




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
    show_answers = exam.show_correct_answers  # Add this line
    return render(request, 'exams/results.html', {
        'exam': exam,
        'attempt': attempt,
        'user_answers': user_answers,
        'show_answers': show_answers  # Pass to template
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

@staff_member_required
@login_required
def publish_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST' and not exam.is_published:
        try:
            exam.is_published = True
            exam.save(update_fields=['is_published'])
            messages.success(request, "Exam published. Students can now see and take this exam.")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('exams:grading_period_exam_list')

@staff_member_required
def unpublish_exam(request, exam_id):
    """Unpublish an exam to hide it from students."""
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST' and exam.is_published:
        exam.is_published = False
        exam.save(update_fields=['is_published'])
        messages.warning(request, "Exam unpublished. Students can no longer see or take this exam. Previously submitted attempts are kept.")
    return redirect('exams:view_exam', exam_id=exam.id)
