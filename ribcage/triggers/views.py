from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from ribcage.phase.check import phase_window
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from ribcage.triggers import fetch, stored, warnings, watched
from ribcage.triggers.client import NotAnswering

# Every phase but RUN, where no list is kept in view (docs/design.md §4.2, #107).
WRITING = (Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK)
# The section a plain post was made in, so the reloaded page keeps it open (#107).
OPENED = "warnings_opened"


def built_page(voter):
    """The page with each topic's films, from the pool or the ballot by the phase, as the row's swap must carry the same (#109)."""
    vocabulary, phase = stored.stored_vocabulary(), current()
    topic_ids = {topic.topic_id for topic in vocabulary.topics}
    nobody = warnings.NOBODY_IN_POOL if stored.shows_pool(phase) else warnings.NOBODY_ON_BALLOT
    return warnings.page(vocabulary, watched.ticked_ids(voter), stored.carriers_in(phase, topic_ids), nobody)


@require_safe
def warnings_page(request):
    # The page is unreachable in RUN, as Welcome sends a stray visitor on (#75, #107).
    if current() is Phase.RUN:
        return redirect("phase_page")
    available = True
    try:
        # The fetch is a read's, made outside any write lock (#74, #107).
        fetch.ensure_vocabulary()
    except NotAnswering:
        available = False
    page = built_page(request.user) if available else None
    return render(request, "triggers/warnings.html", {"page": page, "opened": request.session.pop(OPENED, None)})


@phase_window(*WRITING)
@require_POST
def tick(request):
    """Tick or untick one topic: its id in the body, never in an address, so no proxy log holds it (#16, #107)."""
    topic_id, ticked = request.POST.get("topic", ""), request.POST.get("ticked")
    if not (topic_id.isascii() and topic_id.isdecimal() and watched.is_a_topic_id(int(topic_id))) or ticked not in {"1", "0"}:
        return HttpResponseBadRequest()
    topic_id = int(topic_id)
    watched.set_ticked(request.user, topic_id, ticked == "1")
    page = built_page(request.user)
    section = page.section_of(topic_id)
    # Only htmx swaps in place; a plain post reloads the page, at the section it was made in (#88, #107).
    if request.headers.get("HX-Request") != "true":
        if section is None:
            return redirect("warnings")
        request.session[OPENED] = section.anchor
        return redirect(f"{reverse('warnings')}#{section.anchor}")
    row = None if section is None else next(each for each in section.rows if each.topic_id == topic_id)
    return render(request, "triggers/warnings_swap.html", {"page": page, "section": section, "row": row})
