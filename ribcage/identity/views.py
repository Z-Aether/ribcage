from django.contrib.auth import login as sign_in
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from ribcage.identity.forms import JoinCodeForm, LoginForm, RegistrationForm
from ribcage.identity.models import Voter

login = LoginView.as_view(template_name="identity/login.html", authentication_form=LoginForm)

# Outside the wall, so a stale tab's log out lands on login rather than signing in to a GET-less page (#70).
logout = login_not_required(LogoutView.as_view())

# Where a new voter lands; #75 points it at Welcome.
AFTER_REGISTRATION = "home"


def home(request):
    # A plain signed-in placeholder until the phase pages take over / (#70, #74).
    return render(request, "identity/home.html")


def render_code_step(request, form):
    return render(request, "identity/join_code.html", {"form": form})


def render_details_step(request, code, form):
    return render(request, "identity/join_details.html", {"form": form, "code": code})


@login_not_required
@require_http_methods(["GET", "POST"])
def join(request):
    if request.method == "GET":
        return render_code_step(request, JoinCodeForm())
    form = JoinCodeForm(request.POST)
    if not form.is_valid():
        return render_code_step(request, form)
    return render_details_step(request, form.cleaned_data["code"], RegistrationForm())


@login_not_required
@require_http_methods(["GET", "POST"])
def join_details(request):
    # The code rides in a hidden field, so a GET or a code that fails again falls back to the first step (#72).
    code_form = JoinCodeForm(request.POST if request.method == "POST" else None)
    if request.method == "GET" or not code_form.is_valid():
        return render_code_step(request, code_form if request.method == "POST" else JoinCodeForm())
    code = code_form.cleaned_data["code"]
    form = RegistrationForm(request.POST)
    if form.is_valid():
        try:
            voter = Voter.objects.create_voter(form.cleaned_data["display_name"], form.cleaned_data["password"])
        except ValidationError as error:
            form.add_error("display_name", error)
        else:
            sign_in(request, voter)
            return redirect(AFTER_REGISTRATION)
    return render_details_step(request, code, form)
