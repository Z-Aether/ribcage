"""The phase check: each voter write declares the phases it may land in, and a post from outside them is refused (#34, #78)."""

from functools import wraps

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from ribcage.phase.history import current

# The reads require_safe allows; OPTIONS and TRACE are checked, as CSRF lets them through unchecked (#78).
READS = {"GET", "HEAD"}


def phase_window(*phases):
    """Refuse a write to the view unless the current phase is one of `phases`, reloading the tab into the current phase.

    The view runs inside the write lock: fetch before the post, never inside it. On a class view, decorate `dispatch` (#78).
    """
    window = frozenset(phases)

    def declare(view):
        @wraps(view)
        def checked(request, *args, **kwargs):
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
    if request.headers.get("HX-Request") == "true":
        # HX-Redirect rather than HX-Refresh: the phase page, not the tab's own address, as a plain post lands (#78).
        return HttpResponse(headers={"HX-Redirect": reverse("phase_page")})
    return redirect("phase_page")
