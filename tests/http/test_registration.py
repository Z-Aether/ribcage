import re

import pytest
from django.contrib.auth import get_user
from django.templatetags.static import static

from ribcage.identity.models import Voter
from ribcage.phase.order import PHASES, Phase
from tests.http.test_phase import PAGE_HEADINGS, walk_to

PASSWORD = "popcorn-before-midnight"
CODE = "local-join-code"


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.JOIN_CODE = CODE


def enter_code(client, code=CODE):
    return client.post("/join/", {"code": code})


def register(client, display_name="Sam", password=PASSWORD, again=None, code=CODE, **extra):
    return client.post(
        "/join/details/",
        {"code": code, "display_name": display_name, "password": password, "password_again": password if again is None else again},
        **extra,
    )


def test_a_wrong_code_is_refused_and_nothing_else_is_shown(client, db):
    response = enter_code(client, "not-the-code")

    assert response.status_code == 200
    assert "That isn&#x27;t the join code." in response.text
    assert 'name="display_name"' not in response.text
    assert "not-the-code" not in response.text.replace('value="not-the-code"', "")


def test_a_non_ascii_guess_is_refused_rather_than_failing(client, db):
    assert 'name="display_name"' not in enter_code(client, "kôd").text


def test_a_right_code_shows_the_second_step_carrying_the_code_in_a_hidden_field(client, db):
    response = enter_code(client)

    assert 'name="display_name"' in response.text
    assert f'<input type="hidden" name="code" value="{CODE}">' in response.text
    assert CODE not in response.headers.get("Location", "")


def test_the_code_is_trimmed_like_a_paste_from_a_chat(client, db):
    assert 'name="display_name"' in enter_code(client, f"  {CODE}\n").text


def test_success_creates_the_voter_signs_them_in_and_redirects(client, db):
    response = register(client, " Sam  Q ")

    assert response.status_code == 302
    assert response.headers["Location"] == "/welcome/"
    voter = Voter.objects.get()
    assert voter.display_name == "Sam Q"
    assert voter.check_password(PASSWORD)
    assert get_user(client) == voter


def test_registering_does_not_sign_out_or_touch_anyone_else(client, db):
    Voter.objects.create_voter("Ada", PASSWORD)
    register(client)

    assert Voter.objects.count() == 2


def test_a_name_taken_in_another_case_is_refused_with_the_taken_message(client, db):
    Voter.objects.create_voter("Sam", PASSWORD)

    response = register(client, "SAM")

    assert response.status_code == 200
    assert "That display name is taken." in response.text
    assert Voter.objects.count() == 1
    assert not get_user(client).is_authenticated


def test_an_invalid_name_is_refused(client, db):
    response = register(client, "x" * 21)

    assert "at most 20 characters" in response.text
    assert Voter.objects.count() == 0


@pytest.mark.parametrize("weak", ["short", "password", "12345678901"])
def test_a_weak_password_is_refused_by_djangos_checks(client, db, weak):
    response = register(client, "Sam", weak)

    assert response.status_code == 200
    assert "This password is" in response.text
    assert Voter.objects.count() == 0


def test_the_similarity_check_compares_against_the_display_name(client, db):
    response = register(client, "Cinephile", "cinephile1")

    assert "too similar" in response.text
    assert Voter.objects.count() == 0


def test_two_different_passwords_are_refused(client, db):
    response = register(client, again="something-else-entirely")

    assert "The two passwords differ." in response.text
    assert Voter.objects.count() == 0


def test_a_refused_second_step_keeps_the_code_and_the_typed_name_but_never_the_password(client, db):
    response = register(client, "Sam", "hunter2-hunter2", again="different-one")

    assert f'name="code" value="{CODE}"' in response.text
    assert 'value="Sam"' in response.text
    assert "hunter2" not in response.text


@pytest.mark.parametrize("code", ["tampered", ""])
def test_a_tampered_or_blank_code_on_the_second_submit_creates_no_voter(client, db, code):
    response = register(client, code=code)

    assert 'name="display_name"' not in response.text
    assert Voter.objects.count() == 0
    assert not get_user(client).is_authenticated


def test_a_missing_code_on_the_second_submit_creates_no_voter(client, db):
    response = client.post("/join/details/", {"display_name": "Sam", "password": PASSWORD, "password_again": PASSWORD})

    assert Voter.objects.count() == 0
    assert 'name="display_name"' not in response.text


def test_the_code_is_checked_in_constant_time(client, db, monkeypatch):
    seen = []
    import secrets

    real = secrets.compare_digest
    monkeypatch.setattr(secrets, "compare_digest", lambda a, b: seen.append((a, b)) or real(a, b))

    enter_code(client, "guess")

    assert seen == [(b"guess", CODE.encode())]


def test_rotating_the_code_signs_nobody_out(client, db, settings):
    register(client)
    settings.JOIN_CODE = "a-new-code"

    assert client.get("/").status_code == 200


def test_registration_has_no_throttle(client, db):
    for _ in range(12):
        assert "That isn&#x27;t the join code." in enter_code(client, "guess").text
    assert 'name="display_name"' in enter_code(client).text


def test_the_get_of_the_second_step_shows_the_code_step(client, db):
    response = client.get("/join/details/")

    assert response.status_code == 200
    assert 'name="code"' in response.text and 'name="display_name"' not in response.text


def test_the_pages_link_between_login_and_registration(client):
    assert 'href="/join/"' in client.get("/login/").text
    assert 'href="/login/"' in client.get("/join/").text
    assert 'href="/login/"' in enter_code(client).text


def test_the_pages_wear_the_voter_skin(client, db):
    assert '<body data-skin="voter">' in client.get("/join/").text
    assert '<body data-skin="voter">' in enter_code(client).text


def test_the_new_voter_can_log_out_and_sign_in_again(client, db):
    register(client)
    client.post("/logout/")

    response = client.post("/login/", {"username": "sam", "password": PASSWORD})

    assert response.headers["Location"] == "/"


EXIT_LABELS = {
    Phase.SUGGEST: "Suggest films",
    Phase.APPROVE: "See the suggestions",
    Phase.VOTE: "Vote",
    Phase.PICK: "See the scores",
    Phase.RUN: "Follow the evening",
}


@pytest.mark.parametrize("phase", PHASES)
def test_registration_lands_on_welcome_whose_exit_names_and_links_the_current_phase_page(client, db, phase):
    walk_to(phase)

    response = register(client, follow=True)

    assert response.redirect_chain == [("/welcome/", 302)]
    assert "<h1>Welcome</h1>" in response.text
    exit_link = re.search(r'<a ([^>]*class="button"[^>]*)>([^<]*)</a>', response.text)
    assert exit_link.group(2).strip() == EXIT_LABELS[phase]
    assert 'href="/"' in exit_link.group(1)
    assert f"<h1>{PAGE_HEADINGS[phase]}</h1>" in client.get("/").text


def test_a_later_visit_to_welcome_shows_the_phase_page(client, db):
    register(client)
    client.get("/welcome/")

    response = client.get("/welcome/", follow=True)

    assert response.redirect_chain == [("/", 302)]
    assert "<h1>Suggest films</h1>" in response.text


def test_welcome_is_not_shown_to_a_voter_who_did_not_just_register(client, db):
    client.force_login(Voter.objects.create_voter("Ada"))

    assert client.get("/welcome/", follow=True).redirect_chain == [("/", 302)]


def test_welcome_says_the_admin_and_host_can_read_a_watched_list(client, db):
    text = register(client, follow=True).text

    assert "admin and the host" in text and "technically read" in text


def test_the_second_step_wires_its_second_field_to_the_live_match_line(client, db):
    page = enter_code(client).text

    assert 'data-confirms-password="id_password"' in page
    assert 'id="id_password"' in page
    assert f'src="{static("components/password-match.js")}"' in page
