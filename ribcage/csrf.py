"""The CSRF refusal: a same-origin post whose token went stale, as a login in another tab rotates it, reloads its tab (#76)."""

from urllib.parse import urlsplit

from django.conf import settings
from django.middleware.csrf import REASON_CSRF_TOKEN_MISSING, REASON_NO_CSRF_COOKIE, CsrfViewMiddleware
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.csrf import csrf_failure

from ribcage.reload import reload_the_tab

# Origin and Referer are checked before the token, so a cross-site post stays a 403; a wrong token has no constant, so Django's builder spells it (#76).
STALE_TOKEN_REASONS = frozenset(
    {
        REASON_NO_CSRF_COOKIE,
        REASON_CSRF_TOKEN_MISSING,
        *(CsrfViewMiddleware._bad_token_message(None, "incorrect", source) for source in ["POST", settings.CSRF_HEADER_NAME]),
    }
)


def the_page_it_came_from(request):
    """The path of a Referer on this very host, or the phase page: never another host, nor more than a path (#76)."""
    host = request.get_host()
    referer = request.headers.get("Referer", "")
    if urlsplit(referer).netloc == host and url_has_allowed_host_and_scheme(referer, {host}, require_https=request.is_secure()):
        page = urlsplit(referer).path or "/"
        # A path such as //elsewhere.example would leave the host, so it is checked as a URL in its own right (#76).
        if url_has_allowed_host_and_scheme(page, {host}):
            return page
    return "/"


def reload_on_a_stale_token(request, reason=""):
    """Django's 403 for a cross-site post, and a reload for a stale or missing token, so neither writes (#76)."""
    if reason not in STALE_TOKEN_REASONS:
        return csrf_failure(request, reason=reason)
    return reload_the_tab(request, the_page_it_came_from(request))
