from django.contrib.auth import login as sign_in
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeDoneView, PasswordChangeView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_http_methods

from ribcage.identity import admin_session
from ribcage.identity.forced_change import reachable_before_the_change
from ribcage.identity.forms import AdminLoginForm, ChangePasswordForm, JoinCodeForm, LoginForm, RegistrationForm
from ribcage.identity.models import Voter
from ribcage.phase.check import account_action

login = LoginView.as_view(template_name="identity/login.html", authentication_form=LoginForm)

# Outside the wall, so a stale tab's log out lands on login rather than signing in to a GET-less page (#70).
logout = account_action(login_not_required(LogoutView.as_view()))

# Django's view keeps this session and, through the session hash, ends the voter's others (#37, #73).
change_password = reachable_before_the_change(
    account_action(
        PasswordChangeView.as_view(
            template_name="identity/change_password.html",
            form_class=ChangePasswordForm,
            success_url=reverse_lazy("password_changed"),
        )
    )
)
password_changed = PasswordChangeDoneView.as_view(template_name="identity/password_changed.html")

# Where a new voter lands (#75, #134).
AFTER_REGISTRATION = "how_it_works"


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
    if request.method == "GET":
        return render_code_step(request, JoinCodeForm())
    code_form = JoinCodeForm(request.POST)
    if not code_form.is_valid():
        return render_code_step(request, code_form)
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


@login_not_required
@require_http_methods(["GET", "POST"])
def admin_login(request):
    destination = request.POST.get("next", request.GET.get("next", ""))
    form = AdminLoginForm(request.POST if request.method == "POST" else None)
    if not form.is_valid():
        return render(request, "identity/admin_login.html", {"form": form, "next": destination})
    safe = url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    response = redirect(destination if safe else "console")
    admin_session.sign_in(request, response)
    return response


class AdminLogout(View):
    http_method_names = ["post"]

    def post(self, request):
        response = redirect("admin_login")
        admin_session.sign_out(request, response)
        return response


# Outside both walls, like the voter's log out, so a stale tab's lands on the admin login (#70, #76).
admin_logout = login_not_required(AdminLogout.as_view())
