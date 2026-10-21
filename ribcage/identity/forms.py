from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        # Never which of the two, and never Django's hint that case matters, since it doesn't here (#16, #69).
        "invalid_login": "The display name or the password is wrong.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)
