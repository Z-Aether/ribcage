"""The forced change: after the admin's reset, a voter reaches only the change-password form and log out until they set their own (#28, #80)."""

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


def reachable_before_the_change(view):
    """Mark the one voter page a voter whose password was reset may still reach (#80)."""
    view.reachable_before_the_change = True
    return view


class ForcedChangeMiddleware(MiddlewareMixin):
    """Sends every other voter request, a post or an htmx request included, to the change form, before its view runs (#80)."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Public and admin views sit outside the voter wall, so the session is never read there, and public pages stay at zero queries (#73, #76).
        if getattr(view_func, "login_required", True) is False or getattr(view_func, "reachable_before_the_change", False):
            return None
        # The login wall ran first, so the voter is already loaded.
        if not getattr(request.user, "must_change_password", False):
            return None
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(headers={"HX-Redirect": reverse("change_password")})
        return redirect("change_password")
