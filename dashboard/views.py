import io
import datetime
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from lessons.models import Lesson, LessonProgress
from quizzes.models import Quiz, QuizAttempt
from exams.models import Exam, ExamAttempt
from .models import StudentProgress, ActivityLog
from django.db.models import Q, Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from django.template.defaultfilters import floatformat
from docx import Document
import docx.shared
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from django.contrib.auth import get_user_model
import os
from django.conf import settings

TEMPLATE_PATH = "media/templates/RANKING_TEMPLATE.docx"

GRADING_PERIODS = [
    ('prelim', 'Prelim'),
    ('midterm', 'Midterm'),
    ('prefinal', 'Prefinal'),
    ('final', 'Final'),
]

def get_period_label(period_value):
    for val, label in GRADING_PERIODS:
        if val == period_value:
            return label
    return period_value

def has_grading_period_field(model):
    return 'grading_period' in [f.name for f in model._meta.get_fields()]

@login_required
def dashboard(request):
    if request.user.is_staff:
        return admin_dashboard(request)
    return student_dashboard(request)

@login_required
def student_dashboard(request):
    user = request.user

    grading_periods = GRADING_PERIODS
    period_stats = {}

    quiz_points_qs = QuizAttempt.objects.filter(
        user=user,
        completed=True,
        quiz__is_archived=False 
    )
    exam_points_qs = ExamAttempt.objects.filter(user=user, completed=True)
    total_quiz_points = quiz_points_qs.aggregate(
        s=Sum('raw_points')
    )['s']
    if total_quiz_points is None:
        total_quiz_points = quiz_points_qs.aggregate(s=Sum('score'))['s'] or 0

    total_exam_points = exam_points_qs.aggregate(
        s=Sum('raw_points')
    )['s']
    if total_exam_points is None:
        total_exam_points = exam_points_qs.aggregate(s=Sum('score'))['s'] or 0

    from django.contrib.auth import get_user_model
    User = get_user_model()
    all_students = User.objects.filter(is_staff=False)
    student_totals = []
    for student in all_students:
        quiz_qs = QuizAttempt.objects.filter(
            user=student,
            completed=True,
            quiz__is_archived=False  
        )
        exam_qs = ExamAttempt.objects.filter(user=student, completed=True)
        stu_quiz_points = quiz_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_quiz_points is None:
            stu_quiz_points = quiz_qs.aggregate(s=Sum('score'))['s'] or 0
        stu_exam_points = exam_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_exam_points is None:
            stu_exam_points = exam_qs.aggregate(s=Sum('score'))['s'] or 0
        student_totals.append({
            'user_id': student.id,
            'total_points': (stu_quiz_points or 0) + (stu_exam_points or 0)
        })
    sorted_students = sorted(student_totals, key=lambda x: x['total_points'], reverse=True)
    overall_rank = None
    for idx, stu in enumerate(sorted_students, 1):
        if stu['user_id'] == user.id:
            overall_rank = idx
            break
    total_students = all_students.count()

    for period_value, period_label in grading_periods:
        lessons_in_period = Lesson.objects.filter(grading_period=period_value, is_active=True)
        total_lessons = lessons_in_period.count()
        lessons_read_count = LessonProgress.objects.filter(
            user=user,
            lesson__grading_period=period_value,
            completed=True,
            lesson__is_active=True
        ).count() if total_lessons > 0 else 0

        lessons_progress_percent = round(lessons_read_count / total_lessons * 100, 1) if total_lessons else 0

        quizzes_answered_count = 0
        quiz_result_list = []
        if has_grading_period_field(QuizAttempt):
            quiz_q = Q(user=user, completed=True, grading_period=period_value)
            quizzes_attempts_qs = QuizAttempt.objects.filter(quiz_q, quiz__is_archived=False).select_related('quiz')
            quizzes_answered_count = quizzes_attempts_qs.count()
            for qa in quizzes_attempts_qs:
                all_users_attempts = QuizAttempt.objects.filter(
                    quiz=qa.quiz,
                    completed=True,
                    grading_period=period_value,
                    quiz__is_archived=False
                ).order_by('-score')
                all_scores = list(all_users_attempts.values_list('score', flat=True))
                placer = all_scores.index(qa.score) + 1 if qa.score in all_scores else None
                top_score = all_scores[0] if all_scores else None
                badge = placer == 1 and qa.score == top_score
                earned_points = getattr(qa, "raw_points", None)
                total_points = getattr(qa, "total_points", None)
                max_score = getattr(qa.quiz, 'max_score', 100)
                score_percent = round((qa.score / max_score) * 100, 1) if max_score else 0
                quiz_result_list.append({
                    'quiz_title': qa.quiz.title,
                    'score': qa.score,
                    'total_score': max_score,
                    'earned_points': earned_points,
                    'total_points': total_points,
                    'score_percent': score_percent,
                    'placer': placer,
                    'badge': badge,
                    'raw_score': qa.score,  
                })

        exam_result_list = []
        if has_grading_period_field(ExamAttempt):
            exam_q = Q(user=user, completed=True, grading_period=period_value)
            exams_attempts_qs = ExamAttempt.objects.filter(exam_q).select_related('exam')

            for ea in exams_attempts_qs:
                all_users_attempts = ExamAttempt.objects.filter(
                    exam=ea.exam,
                    completed=True,
                    grading_period=period_value
                ).order_by('-score')
                all_scores = list(all_users_attempts.values_list('score', flat=True))
                placer = all_scores.index(ea.score) + 1 if ea.score in all_scores else None
                top_score = all_scores[0] if all_scores else None
                badge = placer == 1 and ea.score == top_score
                earned_points = getattr(ea, "raw_points", None)
                total_points = getattr(ea, "total_points", None)
                max_score = getattr(ea.exam, 'max_score', 100)
                score_percent = round((ea.score / max_score) * 100, 1) if max_score else 0
                status = "passed" if getattr(ea, "passed", False) else "failed"
                exam_result_list.append({
                    'exam_title': ea.exam.title,
                    'score': ea.score,
                    'total_score': max_score,
                    'earned_points': earned_points,
                    'total_points': total_points,
                    'score_percent': score_percent,
                    'placer': placer,
                    'status': status,
                    'badge': badge,
                    'raw_score': ea.score,  
                })

        period_stats[period_value] = {
            'label': period_label,
            'lessons_read_count': lessons_read_count,
            'total_lessons': total_lessons,
            'lessons_progress_percent': lessons_progress_percent,
            'quizzes_answered_count': quizzes_answered_count,
            'quiz_result_list': quiz_result_list,
            'exam_result_list': exam_result_list
        }


    lessons_achievements = []
    lessons_read_period = {}
    for period_value, period_label in grading_periods:
        active_lessons = Lesson.objects.filter(grading_period=period_value, is_active=True).count()
        lessons_read = LessonProgress.objects.filter(
            user=user,
            lesson__grading_period=period_value,
            completed=True,
            lesson__is_active=True
        ).count() if active_lessons > 0 else 0

        lessons_read_period[period_value] = (lessons_read, active_lessons)
        if active_lessons > 0 and lessons_read == active_lessons:
            lessons_achievements.append({
                'type': 'finished_lessons_period',
                'description': f'100% lessons read at {period_label}',
                'icon': 'book'
            })

    active_total_lessons = Lesson.objects.filter(is_active=True).count()
    all_read = LessonProgress.objects.filter(
        user=user,
        lesson__is_active=True,
        completed=True
    ).values('lesson_id').distinct().count()

    if active_total_lessons > 0 and all_read == active_total_lessons:
        lessons_achievements.append({
            'type': 'finished_lessons_all',
            'description': f'100% lessons read (All)',
            'icon': 'bookshelf'
        })

    quiz_achievements = []
    user_quiz_attempts = QuizAttempt.objects.filter(
        user=user,
        completed=True,
        quiz__is_archived=False
    ).select_related('quiz')
    for qa in user_quiz_attempts:
        has_perfect = False
        if hasattr(qa, "raw_points") and hasattr(qa, "total_points") and qa.raw_points is not None and qa.total_points is not None:
            if qa.raw_points == qa.total_points and qa.total_points > 0:
                has_perfect = True
        else:
            max_score = getattr(qa.quiz, 'max_score', 100)
            if qa.score == max_score and max_score > 0:
                has_perfect = True
            elif qa.score >= 100:
                has_perfect = True
        if has_perfect:
            quiz_achievements.append({
                'quiz_title': qa.quiz.title,
                'description': f'Perfect score at {qa.quiz.title}',
                'icon': 'check-circle'
            })

    exam_achievements = []
    user_exam_attempts = ExamAttempt.objects.filter(user=user, completed=True).select_related('exam')
    for ea in user_exam_attempts:
        has_perfect = False
        period = getattr(ea, 'grading_period', None)
        period_label = get_period_label(period)
        if hasattr(ea, "raw_points") and hasattr(ea, "total_points") and ea.raw_points is not None and ea.total_points is not None:
            if ea.raw_points == ea.total_points and ea.total_points > 0:
                has_perfect = True
        else:
            max_score = getattr(ea.exam, 'max_score', 100)
            if ea.score == max_score and max_score > 0:
                has_perfect = True
            elif ea.score >= 100:
                has_perfect = True
        if has_perfect:
            exam_achievements.append({
                'exam_title': ea.exam.title,
                'description': f'Perfect score at {ea.exam.title} ({period_label})',
                'icon': 'star-fill'
            })



    context = {
        'grading_periods': grading_periods,
        'period_stats': period_stats,
        'overall_rank': overall_rank,
        'total_students': total_students,
        'total_quiz_points': total_quiz_points,
        'total_exam_points': total_exam_points,
        'lessons_achievements': lessons_achievements,
        'quiz_achievements': quiz_achievements,
        'exam_achievements': exam_achievements,
    }
    return render(request, 'dashboard/student.html', context)

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to view this page.")
        return redirect('student_dashboard')

    from django.contrib.auth import get_user_model
    User = get_user_model()

    total_users = User.objects.count()
    new_users_week = User.objects.filter(
        date_joined__gte=timezone.now() - timedelta(days=7)
    ).count()
    active_users = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()
    total_lessons = Lesson.objects.count()
    total_quizzes = Quiz.objects.count()
    total_exams = Exam.objects.count()

    recent_activities = ActivityLog.objects.all().order_by('-timestamp')[:10]

    period_stats = {}

    for period_value, period_label in GRADING_PERIODS:
        total_lessons_in_period = Lesson.objects.filter(grading_period=period_value, is_active=True).count()

        quizzes_in_period = Quiz.objects.filter(grading_period=period_value, is_archived=False)
        quizzes_list = [
            {'id': q.id, 'title': q.title}
            for q in quizzes_in_period
        ]

        exams_in_period = Exam.objects.filter(grading_period=period_value)
        exams_list = [
            {'id': e.id, 'title': e.title}
            for e in exams_in_period
        ]

        quiz_rankings = []
        for quiz in quizzes_in_period:
            attempts = (QuizAttempt.objects.filter(
                quiz=quiz, completed=True)
                .select_related('user')
                .order_by('-score', 'user__username'))

            if has_grading_period_field(QuizAttempt):
                attempts = attempts.filter(grading_period=period_value)

            student_best = {}
            for att in attempts:
                stu_id = att.user.id
                score = att.score
                earned_points = getattr(att, "raw_points", None)
                total_points = getattr(att, "total_points", None)
                if total_points is None:
                    total_points = getattr(quiz, 'max_score', 100)
                if earned_points is None:
                    earned_points = score
                if stu_id not in student_best or score > student_best[stu_id]['score']:
                    student_best[stu_id] = {
                        'student_name': att.user.get_full_name() or att.user.username,
                        'score': score,
                        'earned_points': earned_points,
                        'total_points': total_points,
                        'passed': getattr(att, "passed", None) if hasattr(att, "passed") else None
                    }
            ranked = sorted(student_best.values(), key=lambda x: x['score'], reverse=True)
            rankings_rows = []
            last_score = None
            rank = 0
            for idx, row in enumerate(ranked, 1):
                if last_score is None or row['score'] < last_score:
                    rank = idx
                rankings_rows.append({
                    'rank': rank,
                    'student_name': row['student_name'],
                    'score': row['score'],
                    'earned_points': row['earned_points'],
                    'total_points': row['total_points'],
                    'passed': row['passed']
                })
                last_score = row['score']
            quiz_rankings.append({
                'quiz_title': quiz.title,
                'rankings': rankings_rows,
            })

        exam_rankings = []
        for exam in exams_in_period:
            attempts = (ExamAttempt.objects.filter(
                exam=exam, completed=True)
                .select_related('user')
                .order_by('-score', 'user__username'))

            if has_grading_period_field(ExamAttempt):
                attempts = attempts.filter(grading_period=period_value)

            student_best = {}
            for att in attempts:
                stu_id = att.user.id
                score = att.score
                earned_points = getattr(att, "raw_points", None)
                total_points = getattr(att, "total_points", None)
                if total_points is None:
                    total_points = getattr(exam, 'max_score', 100)
                if earned_points is None:
                    earned_points = score
                if stu_id not in student_best or score > student_best[stu_id]['score']:
                    student_best[stu_id] = {
                        'student_name': att.user.get_full_name() or att.user.username,
                        'score': score,
                        'earned_points': earned_points,
                        'total_points': total_points,
                        'passed': getattr(att, "passed", None) if hasattr(att, "passed") else None
                    }
            ranked = sorted(student_best.values(), key=lambda x: x['score'], reverse=True)
            rankings_rows = []
            last_score = None
            rank = 0
            for idx, row in enumerate(ranked, 1):
                if last_score is None or row['score'] < last_score:
                    rank = idx
                rankings_rows.append({
                    'rank': rank,
                    'student_name': row['student_name'],
                    'score': row['score'],
                    'earned_points': row['earned_points'],
                    'total_points': row['total_points'],
                    'passed': row['passed']
                })
                last_score = row['score']
            exam_rankings.append({
                'exam_title': exam.title,
                'rankings': rankings_rows,
            })

        period_stats[period_value] = {
            'label': period_label,
            'total_lessons': total_lessons_in_period,
            'quizzes': quizzes_list,
            'exams': exams_list,
            'quiz_rankings': quiz_rankings,
            'exam_rankings': exam_rankings,
        }

    from django.db.models import Max, Avg
    quiz_stats = QuizAttempt.objects.filter(completed=True).aggregate(
        avg_score=Avg('score'),
        high_score=Max('score')
    )

    all_exam_attempts = ExamAttempt.objects.filter(completed=True)
    total_exam_attempts = all_exam_attempts.count()
    passing_exam_attempts = all_exam_attempts.filter(passed=True).count()

    exam_stats = ExamAttempt.objects.filter(completed=True).aggregate(
        avg_score=Avg('score')
    )

    if total_exam_attempts > 0:
        exam_stats['pass_rate'] = passing_exam_attempts / total_exam_attempts
    else:
        exam_stats['pass_rate'] = 0

    all_students = User.objects.filter(is_staff=False)
    student_totals = []
    for student in all_students:
        quiz_qs = QuizAttempt.objects.filter(
            user=student,
            completed=True,
            quiz__is_archived=False 
        )
        exam_qs = ExamAttempt.objects.filter(user=student, completed=True)
        stu_quiz_points = quiz_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_quiz_points is None:
            stu_quiz_points = quiz_qs.aggregate(s=Sum('score'))['s'] or 0
        stu_exam_points = exam_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_exam_points is None:
            stu_exam_points = exam_qs.aggregate(s=Sum('score'))['s'] or 0
        student_totals.append({
            'user_id': student.id,
            'full_name': f"{student.first_name} {student.last_name}".strip() or student.username,
            'total_points': (stu_quiz_points or 0) + (stu_exam_points or 0),
            'quiz_points': stu_quiz_points or 0,
            'exam_points': stu_exam_points or 0,
        })
    sorted_students = sorted(student_totals, key=lambda x: x['total_points'], reverse=True)
    overall_rankings = []
    for idx, stu in enumerate(sorted_students, 1):
        overall_rankings.append({
            'rank': idx,
            'full_name': stu['full_name'],
            'quiz_points': stu['quiz_points'],
            'exam_points': stu['exam_points'],
            'total_points': stu['total_points'],
        })

    context = {
        'total_users': total_users,
        'new_users_week': new_users_week,
        'active_users': active_users,
        'total_lessons': total_lessons,
        'total_quizzes': total_quizzes,
        'total_exams': total_exams,
        'recent_activities': recent_activities,
        'quiz_stats': quiz_stats,
        'exam_stats': exam_stats,
        'grading_periods': GRADING_PERIODS,
        'period_stats': period_stats,
        'overall_rankings': overall_rankings,
    }
    return render(request, 'dashboard/admin.html', context)




@login_required
def download_rankings_docx(request, period_value=None):
    TEMPLATE_PATH = os.path.join(settings.BASE_DIR, 'media', 'templates', 'RANKING_TEMPLATE.docx')


    from django.contrib.auth import get_user_model
    User = get_user_model()


    tables_to_include = request.GET.getlist('tables[]')
    if not tables_to_include:
        tables_to_include = ['overall', 'quizzes', 'exams']

    period_stats = {}
    for period_value_iter, period_label in GRADING_PERIODS:
        total_lessons_in_period = Lesson.objects.filter(grading_period=period_value_iter, is_active=True).count()

        quizzes_in_period = Quiz.objects.filter(grading_period=period_value_iter, is_archived=False)
        quizzes_list = [
            {'id': q.id, 'title': q.title}
            for q in quizzes_in_period
        ]

        exams_in_period = Exam.objects.filter(grading_period=period_value_iter)
        exams_list = [
            {'id': e.id, 'title': e.title}
            for e in exams_in_period
        ]

        quiz_rankings = []
        for quiz in quizzes_in_period:
            attempts = (QuizAttempt.objects.filter(
                quiz=quiz, completed=True)
                .select_related('user')
                .order_by('-score', 'user__username'))
            if has_grading_period_field(QuizAttempt):
                attempts = attempts.filter(grading_period=period_value_iter)

            student_best = {}
            for att in attempts:
                stu_id = att.user.id
                score = att.score
                earned_points = getattr(att, "raw_points", None)
                total_points = getattr(att, "total_points", None)
                if total_points is None:
                    total_points = getattr(quiz, 'max_score', 100)
                if earned_points is None:
                    earned_points = score
                if stu_id not in student_best or score > student_best[stu_id]['score']:
                    student_best[stu_id] = {
                        'student_name': att.user.get_full_name() or att.user.username,
                        'score': score,
                        'earned_points': earned_points,
                        'total_points': total_points,
                        'passed': getattr(att, "passed", None) if hasattr(att, "passed") else None
                    }
            ranked = sorted(student_best.values(), key=lambda x: x['score'], reverse=True)
            rankings_rows = []
            last_score = None
            rank = 0
            for idx, row in enumerate(ranked, 1):
                if last_score is None or row['score'] < last_score:
                    rank = idx
                rankings_rows.append({
                    'rank': rank,
                    'student_name': row['student_name'],
                    'score': row['score'],
                    'earned_points': row['earned_points'],
                    'total_points': row['total_points'],
                    'passed': row['passed']
                })
                last_score = row['score']
            quiz_rankings.append({
                'quiz_title': quiz.title,
                'rankings': rankings_rows,
            })

        exam_rankings = []
        for exam in exams_in_period:
            attempts = (ExamAttempt.objects.filter(
                exam=exam, completed=True)
                .select_related('user')
                .order_by('-score', 'user__username'))
            if has_grading_period_field(ExamAttempt):
                attempts = attempts.filter(grading_period=period_value_iter)

            student_best = {}
            for att in attempts:
                stu_id = att.user.id
                score = att.score
                earned_points = getattr(att, "raw_points", None)
                total_points = getattr(att, "total_points", None)
                if total_points is None:
                    total_points = getattr(exam, 'max_score', 100)
                if earned_points is None:
                    earned_points = score
                if stu_id not in student_best or score > student_best[stu_id]['score']:
                    student_best[stu_id] = {
                        'student_name': att.user.get_full_name() or att.user.username,
                        'score': score,
                        'earned_points': earned_points,
                        'total_points': total_points,
                        'passed': getattr(att, "passed", None) if hasattr(att, "passed") else None
                    }
            ranked = sorted(student_best.values(), key=lambda x: x['score'], reverse=True)
            rankings_rows = []
            last_score = None
            rank = 0
            for idx, row in enumerate(ranked, 1):
                if last_score is None or row['score'] < last_score:
                    rank = idx
                rankings_rows.append({
                    'rank': rank,
                    'student_name': row['student_name'],
                    'score': row['score'],
                    'earned_points': row['earned_points'],
                    'total_points': row['total_points'],
                    'passed': row['passed']
                })
                last_score = row['score']
            exam_rankings.append({
                'exam_title': exam.title,
                'rankings': rankings_rows,
            })

        period_stats[period_value_iter] = {
            'label': period_label,
            'total_lessons': total_lessons_in_period,
            'quizzes': quizzes_list,
            'exams': exams_list,
            'quiz_rankings': quiz_rankings,
            'exam_rankings': exam_rankings,
        }

    all_students = User.objects.filter(is_staff=False)
    student_totals = []
    for student in all_students:
        quiz_qs = QuizAttempt.objects.filter(
            user=student,
            completed=True,
            quiz__is_archived=False
        )
        exam_qs = ExamAttempt.objects.filter(user=student, completed=True)
        stu_quiz_points = quiz_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_quiz_points is None:
            stu_quiz_points = quiz_qs.aggregate(s=Sum('score'))['s'] or 0
        stu_exam_points = exam_qs.aggregate(s=Sum('raw_points'))['s']
        if stu_exam_points is None:
            stu_exam_points = exam_qs.aggregate(s=Sum('score'))['s'] or 0
        student_totals.append({
            'user_id': student.id,
            'full_name': f"{student.first_name} {student.last_name}".strip() or student.username,
            'total_points': (stu_quiz_points or 0) + (stu_exam_points or 0),
            'quiz_points': stu_quiz_points or 0,
            'exam_points': stu_exam_points or 0,
        })
    sorted_students = sorted(student_totals, key=lambda x: x['total_points'], reverse=True)
    overall_rankings = []
    for idx, stu in enumerate(sorted_students, 1):
        overall_rankings.append({
            'rank': idx,
            'full_name': stu['full_name'],
            'quiz_points': stu['quiz_points'],
            'exam_points': stu['exam_points'],
            'total_points': stu['total_points'],
        })

    def apply_modern_table_style(table, header_color=RGBColor(0xE1, 0xE0, 0xE0)):
        color_hex = str(header_color)
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                for paragraph in cell.paragraphs:
                    if row_idx == 0:
                        for run in paragraph.runs:
                            run.bold = True
                        tc_pr = cell._tc.get_or_add_tcPr()
                        shd_xml = (
                            f'<w:shd {nsdecls("w")}'
                            f' w:val="clear"'
                            f' w:color="auto"'
                            f' w:fill="{color_hex}"/>'
                        )
                        tc_pr.append(parse_xml(shd_xml))
                    if col_idx != 1:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def int_format(value):
        try:
            return str(int(round(float(value))))
        except Exception:
            return str(value)


    def add_docx_heading(doc, text, level=1):
        style_map = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}
        default_styles = ["Heading 1", "Heading 2", "Heading 3", "Title", "Subtitle"]
        style_name = style_map.get(level, "Heading 1")
        for try_style in [style_name] + default_styles:
            if try_style in [s.name for s in doc.styles]:
                return doc.add_paragraph(text, style=try_style)
        p = doc.add_paragraph(text)
        for run in p.runs:
            run.bold = True
            if level == 1:
                run.font.size = docx.shared.Pt(16)
            elif level == 2:
                run.font.size = docx.shared.Pt(14)
            elif level == 3:
                run.font.size = docx.shared.Pt(12)
        return p

    doc = Document(TEMPLATE_PATH)
    add_docx_heading(doc, 'OFFICIAL STUDENT RANKINGS', level=1)
    doc.add_paragraph(f"Generated on: {datetime.date.today().strftime('%B %d, %Y')}")
    doc.add_paragraph()  

    if 'overall' in tables_to_include:
        add_docx_heading(doc, 'Overall Student Rankings', level=2)
        doc.add_paragraph('Based on cumulative quiz and exam points', style='Intense Quote' if 'Intense Quote' in [s.name for s in doc.styles] else None)
        table = doc.add_table(rows=1, cols=5)
        hdr_cells = table.rows[0].cells
        header_texts = ['Rank', 'Student Name', 'Quiz Score', 'Exam Score', 'Total Score']
        for i, text in enumerate(header_texts):
            hdr_cells[i].text = text
        for stu in overall_rankings:
            row_cells = table.add_row().cells
            row_data = [
                f"#{stu['rank']}",
                stu['full_name'],
                int_format(stu['quiz_points']),
                int_format(stu['exam_points']),
                int_format(stu['total_points'])
            ]
            for i, data in enumerate(row_data):
                row_cells[i].text = data
        apply_modern_table_style(table)
        doc.add_page_break()


    periods_to_show = [(p_val, p_label) for p_val, p_label in GRADING_PERIODS
                      if period_value is None or p_val == period_value]
    for p_val, p_label in periods_to_show:
        stats = period_stats[p_val]
        any_period_tables = False

        if 'quizzes' in tables_to_include and stats.get('quiz_rankings'):
            any_period_tables = True
        if 'exams' in tables_to_include and stats.get('exam_rankings'):
            any_period_tables = True

        if not any_period_tables:
            continue

        add_docx_heading(doc, f'{p_label} Period Rankings', level=1)
        doc.add_paragraph()  
        if 'quizzes' in tables_to_include and stats.get('quiz_rankings'):
            add_docx_heading(doc, 'Quiz Rankings', level=2)
            for quiz in stats['quiz_rankings']:
                add_docx_heading(doc, quiz['quiz_title'], level=3)
                quiz_table = doc.add_table(rows=1, cols=5)
                quiz_header = quiz_table.rows[0].cells
                header_texts = ['Rank', 'Student', 'Percentage', 'Score', 'Status']
                for i, text in enumerate(header_texts):
                    quiz_header[i].text = text
                for rank in quiz['rankings']:
                    r = quiz_table.add_row().cells
                    row_data = [
                        f"#{rank['rank']}",
                        rank['student_name'],
                        int_format(rank['score']),
                        f"{int_format(rank['earned_points'])} / {int_format(rank['total_points'])}",
                        "Passed" if rank['passed'] else "Failed"
                    ]
                    for i, data in enumerate(row_data):
                        r[i].text = data
                apply_modern_table_style(quiz_table)
                doc.add_paragraph()

        if 'exams' in tables_to_include and stats.get('exam_rankings'):
            add_docx_heading(doc, 'Exam Rankings', level=2)
            for exam in stats['exam_rankings']:
                add_docx_heading(doc, exam['exam_title'], level=3)
                exam_table = doc.add_table(rows=1, cols=5)
                exam_header = exam_table.rows[0].cells
                header_texts = ['Rank', 'Student', 'Percentage', 'Score', 'Status']
                for i, text in enumerate(header_texts):
                    exam_header[i].text = text
                for rank in exam['rankings']:
                    r = exam_table.add_row().cells
                    row_data = [
                        f"#{rank['rank']}",
                        rank['student_name'],
                        int_format(rank['score']),
                        f"{int_format(rank['earned_points'])} / {int_format(rank['total_points'])}",
                        "Passed" if rank['passed'] else "Failed"
                    ]
                    for i, data in enumerate(row_data):
                        r[i].text = data
                apply_modern_table_style(exam_table)
                doc.add_paragraph()
        if p_val != periods_to_show[-1][0]:
            doc.add_page_break()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    period_suffix = f"_{period_value}" if period_value else ""
    filename = f"Student_Rankings_Report{period_suffix}_{datetime.date.today().isoformat()}.docx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response