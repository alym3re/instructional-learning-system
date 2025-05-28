import random
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.models import User
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.forms import inlineformset_factory
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
from itertools import groupby
from operator import attrgetter
from .models import Quiz, Question, Answer, QuizAttempt, UserAnswer, GRADING_PERIOD_CHOICES, QUESTION_TYPE_CHOICES, LockedQuizPeriod
from .forms import QuizForm, QuestionForm, AnswerForm, AnswerFormSet, FillInTheBlanksForm
from accounts.models import User
section_choices = User.SECTION_CHOICES

QUESTION_TYPE_ORDER = [
    'multiple_choice',
    'true_false',
    'fill_in_the_blanks',
    'identification',
]

def ordered_questions(questions):
    """
    Returns the list or queryset of questions ordered based on QUESTION_TYPE_ORDER.
    """
    # If questions are queryset, convert to list with prefetching
    qs = list(questions) if not isinstance(questions, list) else questions
    type_priority = {t: i for i, t in enumerate(QUESTION_TYPE_ORDER)}
    # Assign a high number for unrecognized types so they're last
    return sorted(qs, key=lambda q: type_priority.get(q.question_type, 99))

def get_questions_grouped_by_type(questions):
    """
    Group a queryset or list of questions by 'question_type' in the desired order.
    Returns a list (in type order) of dicts:
    [
      {
        'type': 'multiple_choice',
        'type_verbose': 'Multiple Choice',
        'questions': [...Questions of this type...]
      },
      ...
    ]
    """
    type_display_verbose = {}
    # Safeguard: look through all questions to map verbose labels
    for q in questions:
        if hasattr(q, 'get_question_type_display'):
            type_display_verbose[q.question_type] = q.get_question_type_display()
        else:
            type_display_verbose[q.question_type] = q.question_type

    # Group questions by type
    questions_by_type = {}
    for q in questions:
        qtype = q.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(q)

    # Create the ordered list of groups
    grouped = []
    for qtype in QUESTION_TYPE_ORDER:
        if qtype in questions_by_type and questions_by_type[qtype]:
            grouped.append({
                "type": qtype,
                "type_verbose": type_display_verbose.get(qtype, qtype.replace("_", " ").title()),
                "questions": questions_by_type[qtype]
            })
    
    # Add any question types not in QUESTION_TYPE_ORDER at the end
    for qtype, qs in questions_by_type.items():
        if qtype not in QUESTION_TYPE_ORDER and qs:
            grouped.append({
                "type": qtype,
                "type_verbose": type_display_verbose.get(qtype, qtype.replace("_", " ").title()),
                "questions": qs
            })
            
    return grouped

def grading_period_list(request):
    periods = GRADING_PERIOD_CHOICES
    period_stats = {}
    user = request.user if request.user.is_authenticated else None
    
    # Load locks
    locked_periods = {lk.period: lk.locked for lk in LockedQuizPeriod.objects.all()}

    for period_value, period_label in periods:
        # Only count published, non-archived quizzes for regular users
        # For staff, show all non-archived quizzes
        if user and user.is_staff:
            quizzes = Quiz.objects.filter(grading_period=period_value, is_archived=False)
            quizzes_for_display = list(quizzes.order_by('-created_at'))
        else:
            quizzes = Quiz.objects.filter(grading_period=period_value, is_published=True, is_archived=False)
            quizzes_for_display = list(quizzes.order_by('-created_at'))
            
        quiz_count = quizzes.count()
        view_count = quizzes.aggregate(total_views=models.Sum("view_count"))["total_views"] or 0

        # Progress: How many quizzes in this period has the user completed?
        progress_percent = 0
        user_completed = 0
        if user:
            done_ids = QuizAttempt.objects.filter(
                user=user, quiz__grading_period=period_value, completed=True
            ).values_list("quiz_id", flat=True)
            user_completed = quizzes.filter(id__in=done_ids).count()
            progress_percent = (user_completed / quiz_count) * 100 if quiz_count > 0 else 0
        
        locked = locked_periods.get(period_value, False)

        period_stats[period_value] = {
            "label": period_label,
            "quiz_count": quiz_count,
            "view_count": view_count,
            "progress_percent": progress_percent,
            "completed_count": user_completed,
            "quizzes": quizzes_for_display,
            "locked": locked,
        }

    context = {
        "periods": periods,
        "period_stats": period_stats,
        "is_admin": user.is_staff if user else False,
    }
    return render(request, "quizzes/grading_period_list.html", context)

def quiz_list_by_period(request, grading_period):
    valid_periods = [c[0] for c in GRADING_PERIOD_CHOICES]
    if grading_period not in valid_periods:
        from django.contrib import messages
        messages.error(request, "Invalid grading period.")
        return redirect('quizzes:grading_period_list')

    # Only show published quizzes to regular users
    if request.user.is_staff:
        quizzes_qs = Quiz.objects.filter(grading_period=grading_period).order_by('-created_at')
    else:
        quizzes_qs = Quiz.objects.filter(grading_period=grading_period, is_published=True, is_archived=False).order_by('-created_at')
    period_display = dict(GRADING_PERIOD_CHOICES)[grading_period]
    paginator = Paginator(quizzes_qs, 12)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    completed_quiz_ids = set()
    latest_attempts = {}  # Store the latest attempt for each quiz
    if request.user.is_authenticated:
        completed_quiz_ids = set(
            QuizAttempt.objects.filter(
                user=request.user, quiz__grading_period=grading_period, completed=True
            ).values_list('quiz_id', flat=True)
        )

        # Get the latest attempt for each quiz in this grading period
        user_attempts = (
            QuizAttempt.objects
            .filter(
                user=request.user,
                quiz__grading_period=grading_period,
                completed=True
            )
            .order_by('-end_time')  # Most recent attempts first
        )
        for attempt in user_attempts:
            if attempt.quiz_id not in latest_attempts:
                latest_attempts[attempt.quiz_id] = attempt
    
    context = {
        'grading_period': grading_period,
        'grading_period_display': period_display,
        'page_obj': page_obj,
        'user': request.user,
        'completed_quiz_ids': completed_quiz_ids,  # let template display "Completed"
        'latest_attempts': latest_attempts,  # Add latest attempts to context
    }
    return render(request, "quizzes/list.html", context)


@login_required
def quiz_list(request):
    return redirect('quizzes:grading_period_list')

@login_required
def view_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_archived=False)
    
    # Check if quiz is published - only staff can view unpublished quizzes
    if not quiz.is_published and not request.user.is_staff:
        messages.error(request, "This quiz is not currently published.")
        return redirect('quizzes:quiz_list_by_period', grading_period=quiz.grading_period)
        
    if hasattr(quiz, 'increment_view_count'):
        quiz.increment_view_count()
    # Get questions in the preferred order
    questions = ordered_questions(quiz.questions.all().prefetch_related('answers'))
    
    # Check if current user has completed this quiz
    completed = False
    attempt = None
    if request.user.is_authenticated:
        attempt = QuizAttempt.objects.filter(user=request.user, quiz=quiz).first()
        completed = attempt.completed if attempt else False
    
    # Leaderboard: all completed attempts, ordered highest score, shortest duration, latest first
    leaderboard_attempts = (
        QuizAttempt.objects
        .filter(quiz=quiz, completed=True)
        .select_related('user')
        .order_by('-score', 'end_time', 'start_time')
    )

    # Get all user attempts for the results modal
    user_attempts = (
        QuizAttempt.objects
        .filter(quiz=quiz, completed=True)
        .select_related('user')
        .order_by('-score', 'end_time', 'start_time')
    )

    # Get SECTION_CHOICES from User model
    section_choices = User.SECTION_CHOICES

    # Pagination for leaderboard (10 per page)
    page = request.GET.get('leaderboard_page', 1)
    leaderboard_paginator = Paginator(leaderboard_attempts, 10)
    try:
        leaderboard_page_obj = leaderboard_paginator.page(page)
    except PageNotAnInteger:
        leaderboard_page_obj = leaderboard_paginator.page(1)
    except EmptyPage:
        leaderboard_page_obj = leaderboard_paginator.page(leaderboard_paginator.num_pages)
    
    questions_by_type = get_questions_grouped_by_type(questions)
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'questions_by_type': questions_by_type,
        'leaderboard_page_obj': leaderboard_page_obj,
        'completed': completed,  # For template logic to block attempt or show DONE
        'user_attempt': attempt,
        # Below: for the results modal
        'user_attempts': user_attempts,
        'section_choices': section_choices,
    }
    
    if quiz.locked and not request.user.is_staff:
        messages.error(request, "This quiz is locked.")
        return redirect('quizzes:grading_period_list')
    return render(request, "quizzes/view.html", context)

@login_required
def create_quiz(request):
    grading_period = request.GET.get('grading_period') or request.POST.get('grading_period')
    grading_period_label = None
    if grading_period:
        grading_period_label = dict(GRADING_PERIOD_CHOICES).get(grading_period)
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to create quizzes.")
        return redirect('quizzes:grading_period_list')
    
    if request.method == 'POST':
        form = QuizForm(request.POST, request.FILES)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.created_by = request.user
            quiz.is_published = False  # Default to unpublished
            quiz.save()
            messages.success(request, 'Quiz created successfully! Add questions before publishing.')
            return redirect('quizzes:add_quiz_questions', quiz_id=quiz.id)
    else:
        form = QuizForm()
    return render(request, 'quizzes/create.html', {
        'form': form,
        'grading_period': grading_period,
        'grading_period_label': grading_period_label,
        })

@login_required
def upload_quiz(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to upload quizzes.")
        return redirect('quizzes:grading_period_list')
    if request.method == 'POST':
        form = QuizForm(request.POST, request.FILES)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.created_by = request.user
            quiz.save()
            messages.success(request, 'Quiz uploaded successfully!')
            return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    else:
        form = QuizForm()
    return render(request, 'quizzes/upload.html', {'form': form})


@login_required
def add_quiz_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not request.user.is_staff or quiz.created_by != request.user:
        messages.error(request, "You don't have permission to edit this quiz.")
        return redirect('quizzes:quiz_list_by_period', grading_period=quiz.grading_period)
        
    # Prevent editing published quizzes
    if quiz.is_published:
        messages.error(request, "You cannot edit questions for a published quiz. Please unpublish it first.")
        return redirect('quizzes:view_quiz', quiz_id=quiz.id)

    error_message = None
    default_question_type = 'multiple_choice'
    
    # Check if we are editing an existing question
    edit_question_id = request.GET.get('edit_question_id') or request.POST.get('edit_question_id')
    edit_question = None
    if edit_question_id:
        try:
            edit_question = quiz.questions.get(id=edit_question_id)
            question_type = edit_question.question_type
        except Question.DoesNotExist:
            edit_question = None
            question_type = request.POST.get('question_type') or request.GET.get('question_type') or default_question_type
    else:
        question_type = request.POST.get('question_type') or request.GET.get('question_type') or default_question_type

    if request.method == 'POST':
        if question_type == 'fill_in_the_blanks':
            if edit_question:
                question_form = FillInTheBlanksForm(request.POST, instance=edit_question)
            else:
                question_form = FillInTheBlanksForm(request.POST)
            answer_formset = None
        else:
            if edit_question:
                question_form = QuestionForm(request.POST, instance=edit_question)
                answer_formset = AnswerFormSet(request.POST, prefix='answers', instance=edit_question)
            else:
                question_form = QuestionForm(request.POST)
                answer_formset = AnswerFormSet(request.POST, prefix='answers', instance=edit_question)
            
        # Process form validation based on question type
        if question_type == 'identification':
            correct_answer = request.POST.get('correct_answer', '').strip()
            if not correct_answer:
                error_message = "Correct answer cannot be blank for Identification type."
                # Let the form show invalid with the error
                questions = quiz.questions.all().prefetch_related('answers')
                questions_by_type = get_questions_grouped_by_type(ordered_questions(questions))
                return render(request, 'quizzes/add_questions.html', {
                    'quiz': quiz,
                    'question_form': question_form,
                    'answer_formset': answer_formset,
                    'questions': questions,
                    'questions_by_type': questions_by_type,
                    'error': error_message,
                    'editing': edit_question,
                })
            # For identification, we only need the question form to be valid
            valid = question_form.is_valid()
        else:
            # For other question types, both forms need to be valid
            valid = question_form.is_valid() and (answer_formset is None or answer_formset.is_valid())

        # In FIB, ensure blank_answers present & valid
        if question_type == 'fill_in_the_blanks' and not question_form.is_valid():
            valid = False

        if valid:
            with transaction.atomic():
                # Handle either editing existing question or creating new one
                if edit_question:
                    # Update existing question
                    question = question_form.save(commit=False)
                    question.quiz = quiz
                    question.question_type = question_type
                    question.save()
                    
                    # Always clear current answers before saving new ones
                    question.answers.all().delete()
                    
                    # Handle answers based on question type
                    if question_type == 'fill_in_the_blanks':
                        blank_answers = question_form.cleaned_data['blank_answers']
                        for blank_answer in blank_answers:
                            Answer.objects.create(
                                question=question,
                                text=blank_answer.strip(),
                                is_correct=True
                            )
                    elif question_type == 'identification':
                        Answer.objects.create(
                            question=question,
                            text=request.POST.get('correct_answer', '').strip(),
                            is_correct=True
                        )
                    else:
                        # For other question types, use the formset to update answers
                        answer_form_objects = answer_formset.save(commit=False)
                        # Save/update answers in form
                        for answer in answer_form_objects:
                            answer.question = question
                            answer.save()
                        answer_formset.save_m2m()
                        
                    messages.success(request, 'Question updated successfully!')
                else:
                    # Create new question
                    question = question_form.save(commit=False)
                    question.quiz = quiz
                    question.question_type = question_type
                    question.save()

                    # For FIB: create correct Answer objects for each blank entry
                    if question_type == 'fill_in_the_blanks':
                        blank_answers = question_form.cleaned_data['blank_answers']
                        for blank_answer in blank_answers:
                            Answer.objects.create(
                                question=question,
                                text=blank_answer.strip(),
                                is_correct=True
                            )
                    elif question_type == 'identification':
                        # For identification questions, create a single correct answer
                        answer = Answer.objects.create(
                            question=question,
                            text=request.POST.get('correct_answer', '').strip(),
                            is_correct=True
                        )
                    else:
                        # For other question types that use the answer formset
                        answers = answer_formset.save(commit=False)
                        for answer in answers:
                            answer.question = question
                            answer.save()
                        answer_formset.save_m2m()
                        
                        # Ensure at least one answer is marked as correct
                        if not any(answer.is_correct for answer in answers):
                            messages.error(request, "At least one answer must be marked as correct.")
                            questions = quiz.questions.all().prefetch_related('answers')
                            questions_by_type = get_questions_grouped_by_type(ordered_questions(questions))
                            return render(request, 'quizzes/add_questions.html', {
                                'quiz': quiz,
                                'question_form': question_form,
                                'answer_formset': answer_formset,
                                'questions': questions,
                                'questions_by_type': questions_by_type,
                                'error': "At least one answer must be marked as correct.",
                                'editing': edit_question,
                            })
                    messages.success(request, 'Question added successfully!')
                return redirect('quizzes:add_quiz_questions', quiz_id=quiz.id)
        else:
            error_message = "Invalid question or answer form"
    else:
        # GET: Show form for ADD or EDIT
        if edit_question:
            if question_type == 'fill_in_the_blanks':
                # For FIB, we need to get the blank answers from the existing question
                blank_answers = list(edit_question.answers.filter(is_correct=True).values_list('text', flat=True))
                question_form = FillInTheBlanksForm(instance=edit_question, initial={
                    'question_type': 'fill_in_the_blanks',
                    'blank_answers': blank_answers,
                })
                answer_formset = None
            elif question_type == 'identification':
                # For identification, get the correct answer
                correct_answer = edit_question.answers.filter(is_correct=True).first()
                question_form = QuestionForm(instance=edit_question)
                answer_formset = None
            else:
                question_form = QuestionForm(instance=edit_question)
                answer_formset = AnswerFormSet(prefix='answers', instance=edit_question)
        else:
            if question_type == 'fill_in_the_blanks':
                question_form = FillInTheBlanksForm(initial={'question_type': 'fill_in_the_blanks'})
                answer_formset = None
            else:
                question_form = QuestionForm(initial={'question_type': question_type})
                answer_formset = AnswerFormSet(prefix='answers')

    # Get questions in the preferred order
    questions = ordered_questions(quiz.questions.all().prefetch_related('answers'))
    questions_by_type = get_questions_grouped_by_type(questions)
    return render(request, 'quizzes/add_questions.html', {
        'quiz': quiz,
        'question_form': question_form,
        'answer_formset': answer_formset,
        'questions': questions,
        'questions_by_type': questions_by_type,
        'error': error_message,
        'editing': edit_question,
    })

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_archived=False)
    
    # Check if quiz is published
    if not quiz.is_published and not request.user.is_staff:
        messages.error(request, "This quiz is not currently published.")
        return redirect('quizzes:quiz_list_by_period', grading_period=quiz.grading_period)
        
    user_attempt = QuizAttempt.objects.filter(user=request.user, quiz=quiz).first()
    if user_attempt and user_attempt.completed:
        messages.info(request, "You have already completed this quiz. You cannot take it again.")
        return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    elif user_attempt is None:
        user_attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz)

    if quiz.locked and not request.user.is_staff:
        messages.error(request, "This quiz is locked.")
        return redirect('quizzes:grading_period_list')

    if request.method == 'POST':
        with transaction.atomic():
            total_points = 0
            total_score = 0
            for question in quiz.questions.all():
                qtype = question.question_type
                user_answer_obj, _ = UserAnswer.objects.get_or_create(attempt=user_attempt, question=question)
                user_answer_obj.is_correct = False

                if qtype.startswith('multiple'):
                    choice_ids = request.POST.getlist(f'question_{question.id}')
                    if qtype == 'multiple_single' and len(choice_ids) > 1:
                        choice_ids = choice_ids[:1]
                    selected_answers = Answer.objects.filter(question=question, id__in=choice_ids)
                    user_answer_obj.selected_answers.set(selected_answers)
                    user_answer_obj.text_answer = None

                elif qtype == 'true_false':
                    answer_val = request.POST.get(f'question_{question.id}')
                    user_answer_obj.selected_answers.clear()
                    user_answer_obj.text_answer = None
                    if answer_val and answer_val.isdigit():
                        selected_answer = Answer.objects.filter(pk=answer_val, question=question).first()
                        if selected_answer:
                            user_answer_obj.selected_answers.add(selected_answer)
                    elif answer_val:
                        user_answer_obj.text_answer = answer_val

                elif qtype == 'identification':
                    answer_text = request.POST.get(f'question_{question.id}_text', '').strip()
                    user_answer_obj.text_answer = answer_text
                    user_answer_obj.selected_answers.clear()

                elif qtype == 'fill_in_the_blanks':
                    blanks = request.POST.getlist(f'question_{question.id}_blank[]')
                    user_answer_obj.text_answer = '|'.join([b.strip() for b in blanks])

                # Scoring logic remains the same
                if qtype == 'fill_in_the_blanks':
                    correct_blanks = question.answers.filter(is_correct=True).values_list('text', flat=True)
                    user_blanks = [b.strip().lower() for b in blanks]
                    n_blanks = len(correct_blanks)
                    per_blank_pts = question.points
                    correct_count = 0
                    for i, correct_answer in enumerate(correct_blanks):
                        if i < len(user_blanks) and user_blanks[i].lower() == correct_answer.lower():
                            correct_count += 1
                    user_answer_obj.partial_score = correct_count
                    user_answer_obj.is_correct = (correct_count == n_blanks)
                    total_points += per_blank_pts * n_blanks
                    total_score += per_blank_pts * correct_count
                else:
                    user_answer_obj.check_answer()
                    total_points += question.points
                    if user_answer_obj.is_correct:
                        total_score += question.points
                user_answer_obj.save()
            
            user_attempt.completed = True
            user_attempt.end_time = timezone.now()
            user_attempt.raw_points = total_score
            user_attempt.total_points = total_points
            user_attempt.score = (total_score / total_points) * 100 if total_points > 0 else 0
            user_attempt.passed = user_attempt.score >= quiz.passing_score
            user_attempt.save()
            messages.success(request, 'Quiz submitted successfully!')
            return redirect('quizzes:quiz_results', attempt_id=user_attempt.id)

    # Get questions grouped by type and shuffled within each type
    questions_by_type = []
    
    # 1. Multiple Choice (shuffled)
    mc_questions = list(quiz.questions.filter(question_type='multiple_choice'))
    random.shuffle(mc_questions)
    if mc_questions:
        questions_by_type.append({
            'type': 'multiple_choice',
            'type_verbose': 'Multiple Choice',
            'questions': mc_questions
        })
    
    # 2. True/False (shuffled)
    tf_questions = list(quiz.questions.filter(question_type='true_false'))
    random.shuffle(tf_questions)
    if tf_questions:
        questions_by_type.append({
            'type': 'true_false',
            'type_verbose': 'True/False',
            'questions': tf_questions
        })
    
    # 3. Fill in the Blanks (shuffled)
    fib_questions = list(quiz.questions.filter(question_type='fill_in_the_blanks'))
    random.shuffle(fib_questions)
    if fib_questions:
        questions_by_type.append({
            'type': 'fill_in_the_blanks',
            'type_verbose': 'Fill in the Blanks',
            'questions': fib_questions
        })
    
    # 4. Identification (shuffled)
    id_questions = list(quiz.questions.filter(question_type='identification'))
    random.shuffle(id_questions)
    if id_questions:
        questions_by_type.append({
            'type': 'identification',
            'type_verbose': 'Identification',
            'questions': id_questions
        })
    
    # Calculate total question count for numbering
    total_questions = sum(len(group['questions']) for group in questions_by_type)
    
    # Create a flat list of questions for global numbering
    flat_questions = []
    for group in questions_by_type:
        for question in group['questions']:
            flat_questions.append({
                'type_verbose': group['type_verbose'],
                'question_type': group['type'],
                'question': question,
            })
    
    return render(request, 'quizzes/take.html', {
        'quiz': quiz,
        'questions_by_type': questions_by_type,
        'flat_questions': flat_questions,        # For globally-incremented numbering
        'total_questions': total_questions,
        'attempt': user_attempt,
        'time_limit': quiz.time_limit * 60 if quiz.time_limit > 0 else None
    })

@login_required
def quiz_results(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
    if not attempt.completed:
        messages.error(request, "This quiz attempt is not completed yet.")
        return redirect('quizzes:grading_period_list')

    # Select related so we can access user_answer.question easily in template
    user_answers = list(attempt.user_answers.select_related('question').all())
    show_answers = attempt.quiz.show_correct_answers or attempt.passed or request.user.is_staff

    # Group and order user_answers for results.html like questions in view.html
    user_answers_by_type = {qtype: [] for qtype in QUESTION_TYPE_ORDER}
    extra_types = {}

    for ua in user_answers:
        qtype = getattr(ua.question, 'question_type', None)
        if qtype in user_answers_by_type:
            user_answers_by_type[qtype].append(ua)
        else:
            extra_types.setdefault(qtype, []).append(ua)

    # Make ordered list of question types with their answers
    sorted_user_answers_by_type = []
    for qtype in QUESTION_TYPE_ORDER:
        answers = user_answers_by_type[qtype]
        if answers:
            sorted_user_answers_by_type.append({
                'question_type': qtype,
                'type_verbose': answers[0].question.get_question_type_display() if answers else qtype.replace("_", " ").title(),
                'answers': answers
            })
    # Add any leftover question types at the end
    for qtype, answers in extra_types.items():
        if qtype and answers:
            sorted_user_answers_by_type.append({
                'question_type': qtype,
                'type_verbose': answers[0].question.get_question_type_display() if answers else qtype.replace("_", " ").title(),
                'answers': answers
            })
            
    # Create a flat list for global ordering and numbering in template
    flat_user_answers = []
    for group in sorted_user_answers_by_type:
        for ua in group['answers']:
            flat_user_answers.append({
                'question_type_verbose': group['type_verbose'],
                'question_type': group['question_type'],
                'user_answer': ua,
                'question': ua.question,
            })

    # Build a submitted_blanks dict {question.id: [list of blank dicts]} for fill-in-the-blanks questions
    submitted_blanks = {}
    for ua in user_answers:
        q = ua.question
        if q.question_type == 'fill_in_the_blanks':
            blanks = []
            correct_answers = list(q.answers.filter(is_correct=True).values_list('text', flat=True))
            user_blanks = [b.strip() for b in (ua.text_answer or '').split('|')]
            for i, correct in enumerate(correct_answers):
                user_answer = user_blanks[i] if i < len(user_blanks) else ''
                is_correct = (user_answer.lower() == correct.lower())
                blanks.append({
                    'user_answer': user_answer or '[No Answer]',
                    'correct': correct,
                    'is_correct': is_correct,
                })
            submitted_blanks[q.id] = blanks

    return render(request, 'quizzes/results.html', {
        'attempt': attempt,
        'user_answers': user_answers,  # Keep for backward compatibility
        'user_answers_by_type': sorted_user_answers_by_type,  # New grouped answers
        'show_answers': show_answers,
        'raw_points': attempt.raw_points,
        'total_points': attempt.total_points,
        'submitted_blanks': submitted_blanks,  # For template to display each blank separately
        'flat_user_answers': flat_user_answers,  # For global question numbering
    })


@login_required
def quiz_history(request):
    attempts = QuizAttempt.objects.filter(
        user=request.user,
        completed=True
    ).select_related('quiz').order_by('-start_time')

    grading_period = request.GET.get('grading_period')
    if grading_period:
        attempts = attempts.filter(quiz__grading_period=grading_period)
    paginator = Paginator(attempts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'quizzes/history.html', {'page_obj': page_obj})

@login_required
def delete_question(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not request.user.is_staff or quiz.created_by != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    question.delete()

    return redirect('quizzes:add_quiz_questions', quiz_id=quiz_id)


@login_required
@user_passes_test(lambda u: u.is_staff)
def archive_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.is_archived = True
    quiz.save(update_fields=['is_archived'])
    messages.success(request, f'Quiz "{quiz.title}" archived.')
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('quizzes:view_quiz', quiz_id=quiz.id)

@login_required
@user_passes_test(lambda u: u.is_staff)
def unarchive_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.is_archived = False
    quiz.save(update_fields=['is_archived'])
    messages.success(request, f'Quiz "{quiz.title}" unarchived.')
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    
@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_period_lock(request, period_value):
    """Allows staff to toggle lock/unlock of a grading period."""
    valid_periods = [c[0] for c in GRADING_PERIOD_CHOICES]
    if period_value not in valid_periods:
        messages.error(request, "Invalid grading period.")
        return redirect('quizzes:grading_period_list')
        
    lock, created = LockedQuizPeriod.objects.get_or_create(period=period_value)
    lock.locked = not lock.locked
    lock.save()
    
    action = "locked" if lock.locked else "unlocked"
    period_display = dict(GRADING_PERIOD_CHOICES)[period_value]
    messages.success(request, f"Period '{period_display}' has been {action}.")
    
    return redirect('quizzes:grading_period_list')

@login_required
@user_passes_test(lambda u: u.is_staff)
def lock_quiz(request, quiz_id):
    """Allows staff to lock a specific quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.locked = True
    quiz.save(update_fields=["locked"])
    messages.success(request, f"Quiz '{quiz.title}' has been locked.")
    return redirect(request.META.get("HTTP_REFERER", "quizzes:grading_period_list"))

@login_required
@user_passes_test(lambda u: u.is_staff)
def unlock_quiz(request, quiz_id):
    """Allows staff to unlock a specific quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.locked = False
    quiz.save(update_fields=["locked"])
    messages.success(request, f"Quiz '{quiz.title}' has been unlocked.")
    return redirect(request.META.get("HTTP_REFERER", "quizzes:grading_period_list"))

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to edit this quiz.")
        return redirect('quizzes:quiz_list_by_period', grading_period=quiz.grading_period)
    
    # Prevent editing published quizzes
    if quiz.is_published:
        messages.error(request, "You cannot edit a published quiz. Please unpublish it first if you need to make changes.")
        return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    
    if request.method == 'POST':
        form = QuizForm(request.POST, request.FILES, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, 'Quiz updated successfully!')
            return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    else:
        form = QuizForm(instance=quiz)
    
    return render(request, 'quizzes/edit.html', {
        'form': form,
        'quiz': quiz
    })

@require_GET
@login_required
def get_question(request, quiz_id, question_id):
    """
    API endpoint to retrieve a question and its answers in JSON format for editing.
    Used for AJAX-based edit-in-place functionality.
    """
    # Security: Only staff and quiz creator can edit questions
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not request.user.is_staff or quiz.created_by != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    
    # For fill_in_the_blanks, extract blank answers
    blank_answers = []
    if question.question_type == 'fill_in_the_blanks':
        blank_answers = list(question.answers.filter(is_correct=True).values_list('text', flat=True))
    
    # Get all answers for the question
    answers_list = list(question.answers.all().order_by('id').values('id', 'text', 'is_correct'))
    
    question_data = {
        'success': True,
        'id': question.id,
        'text': question.text,
        'question_type': question.question_type,
        'points': question.points,
        'explanation': question.explanation,
        'answers': answers_list,
        'blank_answers': blank_answers,
    }
    return JsonResponse(question_data)

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def publish_quiz(request, quiz_id):
    """Publish a quiz to make it available to students."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not quiz.is_published:
        quiz.is_published = True
        quiz.save(update_fields=['is_published'])
        messages.success(request, "Quiz published. Students can now see and take this quiz.")
    return redirect(request.POST.get('next') or reverse('quizzes:view_quiz', args=[quiz.id]))

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def unpublish_quiz(request, quiz_id):
    """Unpublish a quiz to hide it from students."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.is_published:
        quiz.is_published = False
        quiz.save(update_fields=['is_published'])
        messages.warning(request, "Quiz unpublished. Students can no longer see or take this quiz. Previously submitted attempts are kept.")
    return redirect(request.POST.get('next') or reverse('quizzes:view_quiz', args=[quiz.id]))

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def delete_quiz(request, slug):
    """Allow staff to delete a quiz only if archived. Hard delete the Quiz object."""
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.is_archived:
        messages.error(request, "You can only delete archived quizzes.")
        return redirect('quizzes:view_quiz', quiz_id=quiz.id)
    grading_period = quiz.grading_period
    quiz_title = quiz.title
    quiz.delete()
    messages.success(request, f'Quiz \"{quiz_title}\" has been permanently deleted.')

    return redirect('quizzes:quiz_list_by_period', grading_period=grading_period)
