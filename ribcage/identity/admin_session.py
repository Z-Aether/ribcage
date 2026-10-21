"""The admin's session: a row in Django's session store under a cookie of its own, beside a voter's (#8, #76)."""

from functools import wraps
from importlib import import_module

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import redirect_to_login
from django.utils.crypto import constant_time_compare, salted_hmac

COOKIE_NAME = "adminsessionid"
PASSWORD_DIGEST = "admin_password_digest"


def session_store(key=None):
    return import_module(settings.SESSION_ENGINE).SessionStore(key)


def password_digest():
    # Held in the session, so a new ADMIN_PASSWORD ends every admin session, as a voter's reset ends theirs (#8, #37).
    return salted_hmac("ribcage.identity.admin_session", settings.ADMIN_PASSWORD, algorithm="sha256").hexdigest()


def signed_in(request):
    key = request.COOKIES.get(COOKIE_NAME)
    if not key:
        return False
    return constant_time_compare(session_store(key).get(PASSWORD_DIGEST, ""), password_digest())


def sign_in(request, response):
    # Always a fresh key, so a key planted before sign-in never becomes the admin's.
    # The CSRF token is left as it is, unlike a voter's login, so a voter tab open beside it can still post (#76).
    end(request)
    session = session_store()
    session[PASSWORD_DIGEST] = password_digest()
    session.save()
    # The voter session's cookie settings, so both cookies are Secure, HttpOnly, Lax and as long-lived (#31, #60).
    response.set_cookie(
        COOKIE_NAME,
        session.session_key,
        max_age=session.get_expiry_age(),
        domain=settings.SESSION_COOKIE_DOMAIN,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def sign_out(request, response):
    end(request)
    response.delete_cookie(
        COOKIE_NAME,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def end(request):
    if key := request.COOKIES.get(COOKIE_NAME):
        session_store(key).delete()


def admin_required(view):
    """Outside the voter wall and behind the admin's: without the admin session, the admin login (#76)."""

    @login_not_required
    @wraps(view)
    def walled(request, *args, **kwargs):
        if not signed_in(request):
            return redirect_to_login(request.get_full_path(), "admin_login")
        return view(request, *args, **kwargs)

    walled.admin_required = True
    return walled
