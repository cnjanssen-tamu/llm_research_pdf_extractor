from django import template

register = template.Library()

@register.filter(name='filter_by_category')
def filter_by_category(columns, category):
    """Filter columns by category"""
    return [col for col in columns if col.category == category] 