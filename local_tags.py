from django import template
register = template.Library()

@register.simple_tag
def page(format_string, *args, **kwargs):
    return "page content"

@register.simple_tag
def site(format_string, *args, **kwargs):
    return "site content"

@register.simple_tag
def paginate(*args, **kwargs):
    return "<   -- pagination --  >"
