"""The login wall, which an htmx request is refused by reloading the tab, not by following the redirect into its region (#160)."""

from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.urls import reverse

from ribcage.reload import reload_the_tab


class LoginWall(LoginRequiredMiddleware):
    def handle_no_permission(self, request, view_func):
        # A polling page fires unattended, so a session that ended must not morph the login page into the page (#160).
        if request.headers.get("HX-Request") == "true":
            return reload_the_tab(request, reverse("login"))
        return super().handle_no_permission(request, view_func)
