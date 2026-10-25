from django import template

from ribcage.phase.history import current
from ribcage.phase.order import Phase

register = template.Library()


@register.simple_tag(takes_context=True)
def warnings_link_shown(context):
    """The voter header's *My warnings* link shows in every phase but RUN (#27, #107)."""
    # No voter, no link and no query: base.html renders its default header without the database (#49).
    user = context.get("user")
    return user is not None and user.is_authenticated and current() is not Phase.RUN
