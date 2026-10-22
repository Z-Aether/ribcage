import pytest
from django.test import Client, RequestFactory

from ribcage.csrf import the_page_it_came_from
from ribcage.identity.models import Voter
from ribcage.phase.history import current
from ribcage.phase.order import Phase
from tests.http.signing_in import ADMIN_LOGIN, CODE, PASSWORD
from tests.http.test_proxy_boundary import HOST, ORIGIN, at_the_host

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
ELSEWHERE = "https://elsewhere.example"
NEW_PASSWORD = "intermission-at-two"


@pytest.fixture(autouse=True)
def _deployed_hostname(settings):
    # Same-origin, as a tab posts to the site it came from; no trusted origin is needed for it.
    settings.ALLOWED_HOSTS = [HOST]
    settings.CSRF_TRUSTED_ORIGINS = []


class Tab:
    """One tab of a browser that is held to CSRF: the page it loaded, and the token that page handed it."""

    def __init__(self, browser, page):
        self.browser, self.page = browser, page
        self.reload()

    def reload(self):
        response = self.browser.get(self.page, headers=at_the_host())
        assert response.status_code == 200
        self.token = str(response.context["csrf_token"])

    def post(self, action, fields, htmx=False, headers=None):
        """Posted as a browser posts from the tab's page, unless `headers` says otherwise."""
        headers = {"origin": ORIGIN, "referer": f"{ORIGIN}{self.page}"} if headers is None else headers
        if htmx:
            # An htmx post carries the token base.html hands it, in the header (#76).
            return self.browser.post(action, fields, headers=at_the_host(**{"HX-Request": "true", "X-CSRFToken": self.token}, **headers))
        return self.browser.post(action, {**fields, "csrfmiddlewaretoken": self.token}, headers=at_the_host(**headers))


def a_browser():
    return Client(enforce_csrf_checks=True)


def sign_in(browser, display_name="Ada"):
    # From a login tab of its own: Django's login rotates the CSRF token, leaving every other tab's stale (#76).
    response = Tab(browser, "/login/").post("/login/", {"username": display_name, "password": PASSWORD})
    assert response.status_code == 302


def sign_in_as_the_admin(browser, settings):
    response = Tab(browser, ADMIN_LOGIN).post(ADMIN_LOGIN, {"password": settings.ADMIN_PASSWORD})
    assert response.status_code == 302


@pytest.fixture
def ada(db):
    return Voter.objects.create_voter("Ada", PASSWORD)


@pytest.fixture
def browser(ada, settings):
    """Signed in on both sides, as the dev is while running the marathon."""
    browser = a_browser()
    sign_in_as_the_admin(browser, settings)
    sign_in(browser)
    return browser


def change_the_password(tab, htmx=False):
    fields = {"old_password": PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}
    return tab.post("/password/", fields, htmx)


def move_to_approve(tab, htmx=False):
    return tab.post("/console/phase/move/", {"from_phase": SUGGEST, "to_phase": APPROVE}, htmx)


def password_changed(voter):
    voter.refresh_from_db()
    return voter.check_password(NEW_PASSWORD)


def phase_moved(voter):
    return current() is not SUGGEST


# A voter page and an admin page, each with the post it makes and how to tell it wrote.
PAGES_AND_POSTS = [
    ("/password/", change_the_password, password_changed),
    ("/console/phase/", move_to_approve, phase_moved),
]
PAGES_AND_POSTS_IDS = ["voter-page", "admin-page"]


def reloaded(response, htmx):
    """Where the response sends the whole tab, or None where it sends it nowhere."""
    if htmx:
        return response.headers.get("HX-Redirect") if response.status_code == 200 else None
    return response.headers.get("Location") if response.status_code == 302 else None


@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
@pytest.mark.parametrize(("page", "post", "wrote"), PAGES_AND_POSTS, ids=PAGES_AND_POSTS_IDS)
def test_a_post_from_a_tab_opened_before_a_voter_login_elsewhere_reloads_that_tab_and_writes_nothing(
    browser, ada, django_assert_num_queries, page, post, wrote, htmx
):
    tab = Tab(browser, page)
    sign_in(browser)

    with django_assert_num_queries(0):
        response = post(tab, htmx)

    assert reloaded(response, htmx) == page
    assert not wrote(ada)


@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
@pytest.mark.parametrize(("page", "post", "wrote"), PAGES_AND_POSTS, ids=PAGES_AND_POSTS_IDS)
def test_the_same_post_from_the_reloaded_tab_writes(browser, ada, page, post, wrote, htmx):
    tab = Tab(browser, page)
    sign_in(browser)
    post(tab, htmx)

    tab.reload()
    post(tab, htmx)

    assert wrote(ada)


# Each public page with a form, and a post it makes.
PUBLIC_FORMS = [
    ("/login/", {"username": "Ada", "password": PASSWORD}),
    (ADMIN_LOGIN, {"password": "whatever-it-is"}),
    ("/join/", {"code": CODE}),
]


@pytest.mark.parametrize(("page", "fields"), PUBLIC_FORMS, ids=["login", "admin-login", "registration"])
def test_a_post_from_a_public_page_left_open_across_a_login_reloads_it_with_no_queries(
    ada, django_assert_num_queries, page, fields
):
    browser = a_browser()
    tab = Tab(browser, page)
    sign_in(browser)

    with django_assert_num_queries(0):
        response = tab.post(page, fields)

    assert (response.status_code, response.headers["Location"]) == (302, page)


def test_a_post_whose_csrf_cookie_is_gone_reloads_its_tab(browser, ada):
    tab = Tab(browser, "/password/")
    del browser.cookies["csrftoken"]

    response = change_the_password(tab)

    assert (response.status_code, response.headers["Location"]) == (302, "/password/")
    assert not password_changed(ada)


@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
def test_an_htmx_or_plain_post_with_no_token_at_all_reloads_its_tab(browser, htmx):
    tab = Tab(browser, "/console/phase/")
    fields = {"from_phase": SUGGEST, "to_phase": APPROVE}
    headers = at_the_host(origin=ORIGIN, referer=f"{ORIGIN}/console/phase/", **({"HX-Request": "true"} if htmx else {}))

    response = tab.browser.post("/console/phase/move/", fields, headers=headers)

    assert reloaded(response, htmx) == "/console/phase/"
    assert current() is SUGGEST


@pytest.mark.parametrize("stale", [False, True], ids=["current-token", "stale-token"])
@pytest.mark.parametrize(
    "browser_headers",
    [
        {"origin": ELSEWHERE, "referer": f"{ELSEWHERE}/"},
        {"origin": ELSEWHERE, "referer": f"{ORIGIN}/console/phase/"},
        {"origin": f"http://{HOST}"},
        {"origin": "null"},
    ],
    ids=["other-site", "other-site-with-our-referer", "downgraded-scheme", "opaque-origin"],
)
def test_a_cross_site_post_is_still_refused_with_a_403_and_writes_nothing(browser, browser_headers, stale):
    tab = Tab(browser, "/console/phase/")
    if stale:
        sign_in(browser)

    response = tab.post("/console/phase/move/", {"from_phase": SUGGEST, "to_phase": APPROVE}, headers=browser_headers)

    assert response.status_code == 403
    assert current() is SUGGEST


@pytest.mark.parametrize(
    "referer",
    [f"{ELSEWHERE}/", f"http://{HOST}/console/phase/", None],
    ids=["other-site", "downgraded-scheme", "none"],
)
def test_a_post_with_no_origin_and_no_referer_from_this_site_is_still_refused(browser, referer):
    # With no Origin, Django holds an https post to its Referer, before the token (#31).
    tab = Tab(browser, "/console/phase/")
    sign_in(browser)
    headers = {} if referer is None else {"referer": referer}

    response = tab.post("/console/phase/move/", {"from_phase": SUGGEST, "to_phase": APPROVE}, headers=headers)

    assert response.status_code == 403
    assert current() is SUGGEST


@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
@pytest.mark.parametrize(
    "referer",
    [f"{ELSEWHERE}/steal", f"{ORIGIN}//elsewhere.example/steal", f"{ORIGIN}/\\elsewhere.example/steal"],
    ids=["other-site", "protocol-relative-path", "backslash-path"],
)
def test_a_forged_referer_never_sends_the_tab_off_the_site(browser, referer, htmx):
    tab = Tab(browser, "/console/phase/")
    sign_in(browser)

    fields = {"from_phase": SUGGEST, "to_phase": APPROVE}

    response = tab.post("/console/phase/move/", fields, htmx, headers={"origin": ORIGIN, "referer": referer})

    assert reloaded(response, htmx) == "/"


@pytest.mark.parametrize(
    ("referer", "page"),
    [
        (f"{ORIGIN}/console/phase/", "/console/phase/"),
        (f"{ORIGIN}/console/phase/?arm=APPROVE&from=SUGGEST", "/console/phase/"),
        (f"{ORIGIN}/password/#new", "/password/"),
        (ORIGIN, "/"),
        (f"{ORIGIN}:8443/console/", "/"),
        (f"https://{HOST}.elsewhere.example/console/", "/"),
        (f"https://someone@{HOST}/console/", "/"),
        (f"{ELSEWHERE}/console/", "/"),
        (f"http://{HOST}/console/", "/"),
        (f"{ORIGIN}//elsewhere.example/", "/"),
        (f"{ORIGIN}/\\elsewhere.example/", "/"),
        (f"{ORIGIN}///elsewhere.example/", "/"),
        ("/console/phase/", "/"),
        ("//elsewhere.example/", "/"),
        ("javascript:alert(1)", "/"),
        ("", "/"),
        (None, "/"),
    ],
    ids=[
        "same-origin",
        "query-dropped",
        "fragment-dropped",
        "no-path",
        "other-port",
        "lookalike-host",
        "userinfo",
        "other-site",
        "downgraded-scheme",
        "protocol-relative-path",
        "backslash-path",
        "triple-slash-path",
        "relative",
        "protocol-relative",
        "script",
        "empty",
        "none",
    ],
)
def test_the_tab_reloads_onto_a_path_of_a_same_origin_referer_or_else_the_phase_page(referer, page):
    headers = at_the_host(**({} if referer is None else {"referer": referer}))

    request = RequestFactory().post("/console/phase/move/", headers=headers, secure=True)

    assert the_page_it_came_from(request) == page



@pytest.mark.parametrize(
    ("address", "lands_on"),
    [("/console/roster/reset/", "/console/roster/"), ("/console/backup/upload/", "/console/backup/")],
    ids=["reset-result", "upload-result"],
)
def test_a_reload_onto_the_page_a_post_only_address_showed_a_result_at_lands_on_its_tab(browser, address, lands_on):
    tab = Tab(browser, lands_on)
    sign_in(browser)
    headers = {"origin": ORIGIN, "referer": f"{ORIGIN}{address}"}

    response = tab.post("/console/logout/", {}, headers=headers)
    followed = browser.get(response.headers["Location"], headers=at_the_host(), follow=True)

    assert response.headers["Location"] == address
    assert (followed.status_code, followed.redirect_chain[-1][0]) == (200, lands_on)
