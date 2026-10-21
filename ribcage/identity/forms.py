from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from ribcage.identity import backoff


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
