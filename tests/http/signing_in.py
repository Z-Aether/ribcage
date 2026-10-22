"""The http tests' shared credentials and sign-ins, for voters and the admin (#70, #76)."""

from django.conf import settings

PASSWORD = "popcorn-before-midnight"
CODE = "local-join-code"
ADMIN_LOGIN = "/console/login/"


def log_in(client, display_name, password, **extra):
    return client.post("/login/", {"username": display_name, "password": password, **extra})


def sign_in_as_the_admin(client, password=None, headers=None, **extra):
    fields = {"password": settings.ADMIN_PASSWORD if password is None else password, **extra}
    return client.post(ADMIN_LOGIN, fields, headers=headers)
