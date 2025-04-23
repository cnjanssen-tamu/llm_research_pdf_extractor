# core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter(name='subtract')
def subtract(value, arg):
    """Subtract the arg from the value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.simple_tag
def get_first_matching_result(results, doc_id):
    """Get the first result that matches the document ID"""
    for result in results:
        if result.document.id == doc_id and result.json_result:
            # Handle both cases where case_results is an attribute or dict key
            if isinstance(result.json_result, dict) and 'case_results' in result.json_result:
                return result
    return None