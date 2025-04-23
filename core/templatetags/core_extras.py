from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using the key.
    Usage: {{ mydict|get_item:item.id }}
    """
    if not dictionary:
        return None
    return dictionary.get(key) 