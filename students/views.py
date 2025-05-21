from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Q
from accounts.models import User

@staff_member_required
def student_list(request):
    # Filtering/search parameters
    query = request.GET.get("query", "")
    section = request.GET.get("section", "")
    year_level = request.GET.get("year_level", "")
    
    # Exclude admin and superusers
    students = User.objects.filter(is_superuser=False, is_staff=False)
    if query:
        students = students.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(student_id__icontains=query)
        )
    if section:
        students = students.filter(section=section)
    if year_level:
        students = students.filter(year_level=year_level)
    
    sections = User.objects.filter(is_superuser=False, is_staff=False).values_list("section", flat=True).distinct()
    year_levels = User.YEAR_LEVEL_CHOICES

    return render(request, "students/student_list.html", {
        "students": students,
        "query": query,
        "section": section,
        "year_level": year_level,
        "sections": [s for s in sections if s],
        "year_levels": year_levels
    })
