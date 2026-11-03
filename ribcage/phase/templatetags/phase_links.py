from dataclasses import dataclass

from django import template

from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.triggers import watched

register = template.Library()

# The phases the nag bar nudges in; reopening VOTE brings it back with no rule of its own (#27, #110).
NAGGING = (Phase.SUGGEST, Phase.APPROVE, Phase.VOTE)


@dataclass(frozen=True)
class HeaderLinks:
    warnings_link: bool = False
    nag_bar: bool = False
    to_reveal: bool = False
    to_evening: bool = False


@register.simple_tag(takes_context=True)
def header_links(context):
    """What the voter header offers by the phase, read once: the *My warnings* menu item in every phase but RUN (#27, #107), the nag bar under it (#110), and in RUN the link between the evening and the reveal (#161)."""
    # No voter, no link and no query: base.html renders its default header without the database (#49).
    user = context.get("user")
    if user is None or not user.is_authenticated:
        return HeaderLinks()
    phase = current()
    nag = phase in NAGGING and not context.get("no_nag") and not watched.has_decided(user)
    # The pair of links between the evening and its reveal, in RUN alone, on the two pages that view sets `header_page` for (#27, #161).
    in_run = phase is Phase.RUN
    page = context.get("header_page")
    return HeaderLinks(not in_run, nag, in_run and page == "evening", in_run and page == "reveal")
