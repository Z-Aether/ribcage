from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from ribcage.identity.forms import LoginForm

login = LoginView.as_view(template_name="identity/login.html", authentication_form=LoginForm)

# Outside the wall, so a stale tab's log out lands on login rather than signing in to a GET-less page (#70).
logout = login_not_required(LogoutView.as_view())


def home(request):
    # A plain signed-in placeholder until the phase pages take over / (#70, #74).
    return render(request, "identity/home.html")
