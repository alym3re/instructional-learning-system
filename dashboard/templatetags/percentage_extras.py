from django import template

register = template.Library()

@register.filter
def smart_percent(val):
    """
    Display float as 2 decimals unless .00, then as integer.
    Examples:
        87.00 -> 87
        87.20 -> 87.2
        87.23 -> 87.23
        100   -> 100
    """
    try:
        value = float(val)
    except (TypeError, ValueError):
        return val
    if value == int(value):
        return str(int(value))
    elif round(value * 10) == value * 10:
        # Only one nonzero decimal, e.g. 87.20
        return "{:.1f}".format(value)
    else:
        return "{:.2f}".format(value)