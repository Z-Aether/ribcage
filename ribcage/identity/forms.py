import secrets

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError

from ribcage.identity import backoff, display_names
from ribcage.identity.models import Voter


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        # Never which of the two, and never Django's hint that case matters, since it doesn't here (#16, #69).
        "invalid_login": "The display name or the password is wrong.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)

    def clean(self):
        display_name = self.cleaned_data.get("username")
        if display_name is None or self.cleaned_data.get("password") is None:
            return super().clean()
        key = backoff.voter_key(display_name)
        # Refused unchecked and uncounted, so a friend waits at most one wait at a time (#71).
        refuse_while_waiting(key)
        try:
            cleaned_data = super().clean()
        except ValidationError:
            backoff.record_failure(key)
            refuse_while_waiting(key)
            raise
        backoff.clear(key)
        return cleaned_data


def refuse_while_waiting(key):
    if remaining := backoff.wait(key):
        raise ValidationError(backoff.describe(remaining), code="backoff")


class JoinCodeForm(forms.Form):
    code = forms.CharField(label="Join code", strip=True, widget=forms.TextInput(attrs={"autocomplete": "off", "autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)

    def clean_code(self):
        # Constant time, over bytes so a non-ASCII guess is refused rather than raising (#8, #72).
        typed = self.cleaned_data["code"].encode()
        if not secrets.compare_digest(typed, settings.JOIN_CODE.encode()):
            raise ValidationError("That isn't the join code.", code="wrong_code")
        return self.cleaned_data["code"]


class RegistrationForm(forms.Form):
    display_name = forms.CharField(label="Display name", strip=False, widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}))
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password_again = forms.CharField(label="Password again", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-confirms-password": "id_password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)

    def clean_display_name(self):
        return display_names.clean(self.cleaned_data["display_name"])

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password is None or cleaned_data.get("password_again") is None:
            return cleaned_data
        if password != cleaned_data["password_again"]:
            self.add_error("password_again", ValidationError("The two passwords differ.", code="mismatch"))
        elif "display_name" in cleaned_data:
            try:
                # The similarity check compares against the display name (#37).
                password_validation.validate_password(password, Voter(display_name=cleaned_data["display_name"]))
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned_data


class ChangePasswordForm(PasswordChangeForm):
    # Also the forced change after an admin reset (#37, #80).
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Your current password is wrong.",
        "password_mismatch": "The two passwords differ.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)
        self.fields["old_password"].label = "Current password"
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "New password again"
        self.fields["new_password2"].widget.attrs["data-confirms-password"] = "id_new_password1"
        # The voter skin carries no hint text (#58); a refused password says why.
        for field in self.fields.values():
            field.help_text = ""
