from django import template

register = template.Library()

@register.simple_tag
def length_to_word(iterable):
    n = len(iterable)
    if n == 1:
        return 'one'
    elif n == 2:
        return 'two'
    elif n == 4:
        return 'four'
    elif n == 8:
        return 'eight'
    elif n == 16:
        return 'sixteen'
    else:
        return 'unsupported'

@register.simple_tag
def length_to_margin(iterable):
    n = len(iterable)
    if n == 1:
        return '35%'
    elif n == 2:
        return '20%'
    elif n == 4:
        return '1%'
    elif n == 8:
        return '0%'
    elif n == 16:
        return '0%'
    else:
        return 'unsupported'