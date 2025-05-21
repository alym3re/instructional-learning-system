from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def multiply(a, b):
    """Multiply two numbers in Django templates."""
    try:
        return int(a) * int(b)
    except (ValueError, TypeError):
        try:
            return float(a) * float(b)
        except (ValueError, TypeError):
            return ''

@register.filter
def split(value, key):
    """
    Splits the string by the given key.
    Usage: {{ string|split:"," }}
    """
    if value is None:
        return []
    return str(value).split(key)

@register.filter
def strip(value):
    """
    Strips leading and trailing whitespace from the string.
    Usage: {{ value|strip }}
    """
    if value is None:
        return ''
    return str(value).strip()

@register.filter
def is_python_list_string(val):
    """
    Returns True if val looks like a python list string: starts with [ and ends with ] (ignoring whitespace).
    Usage: {% if value|is_python_list_string %} ...
    """
    if not isinstance(val, str):
        return False
    val = val.strip()
    return val.startswith('[') and val.endswith(']')

@register.filter
def get_at_index(sequence, index):
    """
    Returns the item at the given index in a list or tuple, or '' if out of bounds.
    Usage: {{ mylist|get_at_index:0 }}
    """
    try:
        return sequence[index]
    except (IndexError, TypeError, ValueError):
        return ''
