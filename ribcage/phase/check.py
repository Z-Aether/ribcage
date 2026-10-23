"""The phase check: each voter write declares the phases it may land in, and a post from outside them is refused (#34, #78)."""

from functools import wraps

from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.urls import reverse

from ribcage.phase.history import current
from ribcage.reload import reload_the_tab

# The reads require_safe allows, and the one write a voter makes; CSRF lets OPTIONS and TRACE through unchecked (#78, #88).
READS = {"GET", "HEAD"}
ALLOWED = ["GET", "HEAD", "POST"]


def phase_window(*phases):
    """Refuse a write to the view unless the current phase is one of `phases`, reloading the tab into the current phase.

    Any method but GET, HEAD and POST is answered 405 in every phase, a view that only writes still carries `require_POST`, so a GET of it answers 405 too (#88).
    The view runs inside the write lock: fetch before the post, never inside it. On a class view, decorate `dispatch` (#78).
    """
    window = frozenset(phases)

    def declare(view):
        @wraps(view)
        def checked(request, *args, **kwargs):
            if request.method not in ALLOWED:
                return HttpResponseNotAllowed(ALLOWED)
            if request.method in READS:
                return view(request, *args, **kwargs)
            # One transaction, so a phase move can't land between the check and the write (#14, #74).
            with transaction.atomic():
                if current() not in window:
                    return reload_into_the_current_phase(request)
                return view(request, *args, **kwargs)

        checked.phase_window = window
        return checked

    return declare


def account_action(view):
    """Mark a voter's own account action, such as log out, which works in every phase and so has no window (#78)."""
    view.account_action = True
    return view


def reload_into_the_current_phase(request):
    """The whole tab onto the phase page: the phase check's refusal, and a polling page's answer to a moved phase (#13, #78)."""
    return reload_the_tab(request, reverse("phase_page"))
