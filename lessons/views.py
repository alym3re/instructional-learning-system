import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.conf import settings
from .forms import LessonForm
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView
from .models import Lesson, LessonProgress, LessonAccess, GRADING_PERIOD_CHOICES, PeriodLock
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def grading_period_list(request):
    periods = GRADING_PERIOD_CHOICES
    period_stats = {}
    user = request.user if request.user.is_authenticated else None

    for period_value, period_label in periods:
        lessons = Lesson.objects.filter(grading_period=period_value, is_active=True)
        lesson_count = lessons.count()
        view_count = lessons.aggregate(total_views=Sum("view_count"))["total_views"] or 0

        lock_obj = PeriodLock.objects.filter(grading_period=period_value).first()
        locked = lock_obj.locked if lock_obj else False

        progress_percent = 0
        if user and not user.is_staff and lesson_count > 0:
            completed_count = LessonProgress.objects.filter(
                user=user,
                lesson__grading_period=period_value,
                completed=True,
                lesson__is_active=True
            ).count()
            progress_percent = int((completed_count / lesson_count) * 100)

        period_stats[period_value] = {
            "label": period_label,
            "locked": locked,
            "lesson_count": lesson_count,
            "view_count": view_count,
            "progress_percent": progress_percent,
        }

    context = {
        "periods": periods,
        "period_stats": period_stats,
        "is_admin": user.is_staff if user else False,
    }
    return render(request, "lessons/grading_period_list.html", context)

def lesson_list_by_period(request, grading_period):
    valid_periods = [c[0] for c in GRADING_PERIOD_CHOICES]
    if grading_period not in valid_periods:
        messages.error(request, "Invalid grading period.")
        return redirect('lessons:grading_period_list')

    lock_obj = PeriodLock.objects.filter(grading_period=grading_period).first()
    locked = lock_obj.locked if lock_obj else False
    user = request.user
    if locked and (not user.is_authenticated or not user.is_staff):
        messages.error(request, "This grading period is locked.")
        return redirect('lessons:grading_period_list')

    lessons = Lesson.objects.filter(is_active=True, grading_period=grading_period).order_by('-upload_date')
    period_display = dict(GRADING_PERIOD_CHOICES)[grading_period]
    paginator = Paginator(lessons, 20)  # Increase for more visible cards

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'grading_period': grading_period,
        'grading_period_display': period_display,
        'page_obj': page_obj,
    }
    return render(request, "lessons/list.html", context)

@login_required
def view_lesson(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)
    lock_obj = PeriodLock.objects.filter(grading_period=lesson.grading_period).first()
    locked = lock_obj.locked if lock_obj else False
    if locked and not request.user.is_staff:
        messages.error(request, "This lesson is in a locked grading period.")
        return redirect('lessons:grading_period_list')

    LessonAccess.objects.create(user=request.user, lesson=lesson, access_type='view')
    lesson.increment_view_count()

    progress, created = LessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson
    )
    progress.last_viewed = timezone.now()
    progress.save()

    lesson_access = None
    access_page_obj = None
    if request.user.is_staff:
        lesson_access_qs = LessonAccess.objects.filter(lesson=lesson).order_by('-timestamp')
        paginator = Paginator(lesson_access_qs, 10)
        page_number = request.GET.get('access_page')
        access_page_obj = paginator.get_page(page_number)
        lesson_access = access_page_obj.object_list

    grading_period_display = dict(GRADING_PERIOD_CHOICES).get(lesson.grading_period, lesson.grading_period)

    context = {
        'lesson': lesson,
        'progress': progress,
        'lesson_access': lesson_access,
        'access_page_obj': access_page_obj,
        'grading_period_display': grading_period_display,
    }
    return render(request, "lessons/view.html", context)

@login_required
def upload_lesson(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to upload lessons.")
        return redirect('lessons:grading_period_list')
    initial = {}
    grading_period_display = None
    if request.method == 'GET' and 'grading_period' in request.GET:
        initial['grading_period'] = request.GET['grading_period']
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.uploaded_by = request.user
            lesson.save()
            messages.success(request, 'Lesson uploaded successfully!')
            return redirect('lessons:view_lesson', slug=lesson.slug)
    else:
        form = LessonForm(initial=initial)
    
    # Get current grading period key from the form (either initial or bound data)
    current_gp = form['grading_period'].value()
    if current_gp:
        grading_period_display = dict(GRADING_PERIOD_CHOICES).get(current_gp, current_gp)
        grading_period = current_gp
    else:
        grading_period = None
    
    return render(request, 'lessons/upload.html', {
        'form': form,
        'grading_period_display': grading_period_display,
        'grading_period': grading_period,
    })

@method_decorator(login_required, name='dispatch')
class LessonUpdateView(UpdateView):
    model = Lesson
    form_class = LessonForm
    template_name = "lessons/upload.html"
    def get_object(self, queryset=None):
        return get_object_or_404(Lesson, slug=self.kwargs['slug'])
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to edit lessons.")
            return redirect('lessons:grading_period_list')
        return super().dispatch(request, *args, **kwargs)
    def form_valid(self, form):
        lesson = form.save(commit=False)
        lesson.save()
        messages.success(self.request, 'Lesson updated successfully!')
        return redirect('lessons:view_lesson', slug=lesson.slug)

@login_required
def mark_completed(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug)
    progress, created = LessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson
    )
    progress.completed = not progress.completed
    progress.save()
    action = "completed" if progress.completed else "marked incomplete"
    messages.success(request, f'Lesson {action} successfully!')
    return redirect('lessons:view_lesson', slug=slug)

@login_required
def download_lesson_file(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)
    lock_obj = PeriodLock.objects.filter(grading_period=lesson.grading_period).first()
    locked = lock_obj.locked if lock_obj else False
    if locked and not request.user.is_staff:
        messages.error(request, "This lesson is in a locked grading period.")
        return redirect('lessons:grading_period_list')
    LessonAccess.objects.create(user=request.user, lesson=lesson, access_type='download')
    file_handle = lesson.file
    if not file_handle:
        raise Http404("File not found.")
    response = HttpResponse(file_handle, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file_handle.name.split("/")[-1]}"'
    return response

@user_passes_test(lambda u: u.is_staff)
@require_POST
def archive_lesson(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)
    lesson.is_archived = True
    lesson.save(update_fields=['is_archived'])
    messages.success(request, f'Lesson "{lesson.title}" archived.')
    return redirect('lessons:view_lesson', slug=lesson.slug)

@user_passes_test(lambda u: u.is_staff)
@require_POST
def unarchive_lesson(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)
    lesson.is_archived = False
    lesson.save(update_fields=['is_archived'])
    messages.success(request, f'Lesson "{lesson.title}" unarchived and moved back.')
    # For better UX: redirect to lesson listing for its period
    return redirect('lessons:lesson_list_by_period', grading_period=lesson.grading_period)

def docx_to_html_with_mammoth(docx_path, media_url="/media/", media_root=None):
    try:
        import mammoth
    except ImportError:
        return "<div class='alert alert-danger'>python-mammoth is not installed on the server. Install it with <code>pip install mammoth</code>.</div>"

    # Set up image handling so embedded images are copied and referenced correctly
    extracted_images_dir = None
    image_handler = None
    image_url_base = media_url + "docx-images/"
    if media_root:
        extracted_images_dir = os.path.join(media_root, "docx-images")
        os.makedirs(extracted_images_dir, exist_ok=True)

        def save_image(image):
            image_count = len(os.listdir(extracted_images_dir))
            image_filename = f"img_{image_count + 1}.png"
            image_path = os.path.join(extracted_images_dir, image_filename)
            with image.open() as image_bytes:  # FIX: Open image to get bytes-like object
                with open(image_path, "wb") as f:
                    f.write(image_bytes.read())
            return {"src": image_url_base + image_filename}

        image_handler = mammoth.images.img_element(save_image)

    with open(docx_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file, convert_image=image_handler)
        html = result.value  # The generated HTML
        # Do not append warnings unless you want debug output:
        # messages_ = result.messages

    return html

@login_required
def read_file(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)

    # Check permissions for locked periods
    lock_obj = PeriodLock.objects.filter(grading_period=lesson.grading_period).first()
    locked = lock_obj.locked if lock_obj else False
    if locked and not request.user.is_staff:
        messages.error(request, "This lesson is in a locked grading period.")
        return redirect('lessons:grading_period_list')

    # Record access
    LessonAccess.objects.create(user=request.user, lesson=lesson, access_type='view')

    # Get file extension and absolute URL
    ext = os.path.splitext(lesson.file.name)[1].lower()
    file_absolute_url = request.build_absolute_uri(lesson.file.url)

    # Mammoth conversion for .docx, saves HTML w/ images and styles
    if ext == ".docx" and (not hasattr(lesson, 'html_content') or not lesson.html_content or not lesson.html_content.strip()):
        html_content = docx_to_html_with_mammoth(
            lesson.file.path,
            media_url=settings.MEDIA_URL,
            media_root=settings.MEDIA_ROOT
        )
        lesson.html_content = html_content
        lesson.save(update_fields=['html_content'])

    # Fallback message for .doc
    elif ext == ".doc":
        html_content = (
            "<div class='alert alert-warning'>"
            ".doc format is not supported for preview. Please convert to .docx for inline viewing.</div>"
        )
        if hasattr(lesson, 'html_content'):
            lesson.html_content = html_content
            lesson.save(update_fields=['html_content'])

    return render(request, 'lessons/read_file.html', {
        'lesson': lesson,
        'file_absolute_url': file_absolute_url,
        'ext': ext,
    })

@user_passes_test(lambda u: u.is_staff)
def admin_lesson_access_report(request):
    access_logs = LessonAccess.objects.select_related('lesson', 'user').order_by('-timestamp')
    context = {
        "access_logs": access_logs
    }
    return render(request, "lessons/access_report.html", context)

@user_passes_test(lambda u: u.is_staff)
@require_POST
def toggle_period_lock(request, grading_period):
    lock_obj, created = PeriodLock.objects.get_or_create(grading_period=grading_period)
    lock_obj.locked = not lock_obj.locked
    lock_obj.save()
    return redirect('lessons:grading_period_list')

@user_passes_test(lambda u: u.is_staff)
@require_POST
def delete_lesson(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug, is_active=True)
    if not lesson.is_archived:
        messages.error(request, "You can only delete archived lessons.")
        return redirect('lessons:view_lesson', slug=lesson.slug)
    # Soft delete (set is_active to False):
    lesson.is_active = False
    lesson.save(update_fields=['is_active'])
    messages.success(request, f'Lesson \"{lesson.title}\" has been deleted.')
    return redirect('lessons:lesson_list_by_period', grading_period=lesson.grading_period)