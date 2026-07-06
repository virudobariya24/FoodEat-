from django import template
register = template.Library()

@register.filter
def sub(value, arg):
    """Subtracts arg from value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''
