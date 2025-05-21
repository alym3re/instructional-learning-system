def safe_count(obj):
    """
    Returns the number of items in a queryset or list safely.
    Use this everywhere you need to count something that might be a list or Django queryset.
    """
    # Import here for minimal dependency; avoids import errors if used in non-Django code
    try:
        from django.db.models.query import QuerySet
        from django.db.models.manager import Manager
    except ImportError:
        QuerySet, Manager = None, None

    # Check for QuerySet or Manager (which has .count() and returns a QuerySet for .all())
    if (QuerySet and isinstance(obj, QuerySet)) or (Manager and isinstance(obj, Manager)):
        return obj.count()
    return len(obj)