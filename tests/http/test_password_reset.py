import re

import pytest
from django.contrib.auth import get_user
from django.test import Client

from ribcage.console import views
from ribcage.identity import reset as reset_module
from ribcage.identity.models import Voter
from ribcage.identity.removal import remove
from tests.http.signing_in import PASSWORD
from tests.http.test_roster_tab import TAB, act_links, actions, confirm, signed_in, text

RESET = "/console/roster/reset/"
NEW_PASSWORD = "carved-pumpkin-grin"


def shown_password(page):
    found = re.findall(r'<p class="roster-reset__password"><code>([^<]+)</code></p>', page)
    return found[0] if found else None


def arm(admin, voter):
    return admin.get(TAB, {"reset": voter.pk})


def reset(admin, voter):
    """The admin arms and confirms a reset of `voter`, returning the response that shows the password."""
    action, fields, *_ = confirm(arm(admin, voter).text)
    return admin.post(action, fields)


def stored(voter):
    voter.refresh_from_db()
    return voter.password, voter.must_change_password


def test_every_row_offers_a_reset_armed_by_a_link_to_the_tab(admin, voters):
    page = admin.get(TAB).text

    assert act_links(page, "Reset password…") == [f"{TAB}?reset={voters[name].pk}" for name in ["ada", "Dani", "Hanna"]]


def test_arming_resets_nothing_and_prints_the_confirm_under_the_voters_row(admin, voters):
    dani = voters["Dani"]
    before = stored(dani)
    dani_browser = signed_in(dani)

    page = arm(admin, dani).text

    assert stored(dani) == before
    assert get_user(dani_browser).pk == dani.pk
    action, fields, act, cancel, said = confirm(page)
    assert (action, set(fields), fields["voter"], act, cancel) == (RESET, {"voter", "replacing"}, str(dani.pk), "Reset Dani's password", TAB)
    assert said == (
        "Resetting Dani's password signs them out everywhere and shows you a new one, once, to send them directly. "
        "At their next login they must choose their own before anything else."
    )
    assert re.search(rf'<tr data-voter="{dani.pk}" class="is-armed">.*?</tr>\s*<tr class="ledger__detail">\s*<td colspan="5">\s*<form', page, re.S)
    assert shown_password(page) is None


def test_the_armed_row_gives_up_both_its_arms_and_the_others_keep_theirs(admin, voters):
    page = arm(admin, voters["Dani"]).text

    assert act_links(page, "Reset password…") == [f"{TAB}?reset={voters[name].pk}" for name in ["ada", "Hanna"]]
    assert f"?remove={voters['Dani'].pk}" not in page


def test_an_armed_reset_puts_cancel_in_the_reset_arms_place_and_its_confirm_in_the_row_below(admin, voters):
    page = arm(admin, voters["Dani"]).text

    assert actions(page, voters["Dani"]) == [("cancel", "Reset password…"), ("kept", "Remove…")]
    armed_row = re.search(rf'<tr data-voter="{voters["Dani"].pk}" class="is-armed">(.*?)</tr>', page, re.S)[1]
    assert "<button" not in armed_row


@pytest.mark.parametrize("arming", ["", "x", "-1", "99999999999999999999999"])
def test_an_arm_for_no_voter_arms_nothing(admin, voters, arming):
    response = admin.get(TAB, {"reset": arming})

    assert response.status_code == 200
    assert confirm(response.text) is None


def test_confirming_shows_a_generated_password_that_signs_the_voter_in(admin, voters):
    dani = voters["Dani"]

    response = reset(admin, dani)

    assert response.status_code == 200
    password = shown_password(response.text)
    assert re.fullmatch(r"[a-z2-9]{4}(-[a-z2-9]{4}){3}", password)
    assert stored(dani)[1] is True
    assert dani.check_password(password)
    assert not dani.check_password(PASSWORD)
    assert "Send it to Dani directly. It isn't shown again" in text(response.text)


def test_the_page_showing_the_password_is_never_stored_and_never_an_address(admin, voters):
    response = reset(admin, voters["Dani"])
    password = shown_password(response.text)

    assert "no-store" in response.headers["Cache-Control"]
    assert "Location" not in response.headers
    assert all(password not in value for value in response.headers.values())
    assert '<a href="/console/roster/" aria-current="page">Roster</a>' in response.text


def test_each_reset_generates_a_new_password(admin, voters):
    first = shown_password(reset(admin, voters["Dani"]).text)
    second = shown_password(reset(admin, voters["Dani"]).text)

    assert first != second


def test_the_generated_password_is_drawn_from_the_unambiguous_alphabet():
    assert all(character in reset_module.ALPHABET for character in reset_module.generated_password().replace("-", ""))
    assert not set("0o1li") & set(reset_module.ALPHABET)


def test_the_password_is_shown_once_and_the_tab_never_shows_it_again(admin, voters):
    password = shown_password(reset(admin, voters["Dani"]).text)

    page = admin.get(TAB).text

    assert password not in page
    assert shown_password(page) is None


USED = "That confirm is out of date: Dani's password has changed since it was shown, most likely by that same confirm. It can't be shown again. Reset again for a new one."


def test_a_confirm_posted_twice_resets_once_and_the_second_offers_a_fresh_confirm(admin, voters):
    dani = voters["Dani"]
    action, fields, *_ = confirm(arm(admin, dani).text)
    password = shown_password(admin.post(action, fields).text)
    after_the_reset = stored(dani)

    response = admin.post(action, fields)

    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    assert shown_password(response.text) is None
    assert password not in response.text
    assert stored(dani) == after_the_reset
    again_action, again_fields, act, _, said = confirm(response.text)
    assert (again_action, act) == (RESET, "Reset Dani's password")
    assert said.startswith(USED)
    assert again_fields["replacing"] != fields["replacing"]
    assert dani.check_password(password)


def test_the_fresh_confirm_a_second_post_offers_resets_for_a_new_password(admin, voters):
    dani = voters["Dani"]
    action, fields, *_ = confirm(arm(admin, dani).text)
    first = shown_password(admin.post(action, fields).text)
    again_action, again_fields, *_ = confirm(admin.post(action, fields).text)

    second = shown_password(admin.post(again_action, again_fields).text)

    dani.refresh_from_db()
    assert second and second != first
    assert dani.check_password(second)


def test_the_fresh_confirm_after_an_overlapping_second_post_resets(admin, voters, monkeypatch):
    dani = voters["Dani"]
    action, fields, *_ = confirm(arm(admin, dani).text)
    outdated = Voter.objects.get(pk=dani.pk)  # what an overlapping post read before the first committed
    first = shown_password(admin.post(action, fields).text)
    reads = [outdated]
    real = views.named_voter
    monkeypatch.setattr(views, "named_voter", lambda pk: reads.pop() if reads else real(pk))
    second_page = admin.post(action, fields).text
    monkeypatch.undo()
    again_action, again_fields, *_ = confirm(second_page)

    third = shown_password(admin.post(again_action, again_fields).text)

    dani.refresh_from_db()
    assert third and third != first
    assert dani.check_password(third)


def test_a_reload_that_resubmits_the_confirm_resets_nothing_and_shows_nothing(admin, voters):
    dani = voters["Dani"]
    action, fields, *_ = confirm(arm(admin, dani).text)
    password = shown_password(admin.post(action, fields).text)
    after_the_reset = stored(dani)

    response = admin.post(action, fields, follow=True)

    assert response.redirect_chain == []
    assert shown_password(response.text) is None
    assert USED in text(response.text)
    assert stored(dani) == after_the_reset
    assert dani.check_password(password)


def test_a_confirm_printed_before_the_voter_changed_their_password_resets_nothing(admin, voters):
    dani = voters["Dani"]
    action, fields, *_ = confirm(arm(admin, dani).text)
    dani.set_password(NEW_PASSWORD)
    dani.save()

    response = admin.post(action, fields)

    assert response.status_code == 200
    assert shown_password(response.text) is None
    assert USED in text(response.text)
    assert stored(dani)[1] is False
    assert dani.check_password(NEW_PASSWORD)


def test_a_confirm_for_a_voter_already_removed_resets_nobody(admin, voters):
    action, fields, *_ = confirm(arm(admin, voters["Dani"]).text)
    remove(voters["Dani"])

    response = admin.post(action, fields)

    assert (response.status_code, response.headers["Location"]) == (302, TAB)


@pytest.mark.parametrize("fields", [{}, {"voter": ""}, {"voter": "x"}, {"voter": "99999999999999999999999"}])
def test_a_confirm_that_names_no_voter_resets_nobody(admin, voters, fields):
    before = {name: stored(voter) for name, voter in voters.items()}

    response = admin.post(RESET, fields)

    assert (response.status_code, response.headers["Location"]) == (302, TAB)
    assert {name: stored(voter) for name, voter in voters.items()} == before


@pytest.mark.parametrize("replacing", [None, "", "not-a-digest"])
def test_a_confirm_that_names_no_password_of_theirs_resets_nothing(admin, voters, replacing):
    dani = voters["Dani"]
    before = stored(dani)
    fields = {"voter": dani.pk} if replacing is None else {"voter": dani.pk, "replacing": replacing}

    response = admin.post(RESET, fields)

    assert response.status_code == 200
    assert shown_password(response.text) is None
    assert stored(dani) == before


def test_a_get_at_the_reset_address_goes_to_the_roster_tab(admin):
    response = admin.get(RESET)

    assert (response.status_code, response.headers["Location"]) == (302, "/console/roster/")


@pytest.mark.parametrize("path", ["/", "/password/"])
def test_the_voters_existing_session_ends(admin, voters, path):
    dani_browser = signed_in(voters["Dani"])

    reset(admin, voters["Dani"])

    assert dani_browser.get(path).headers["Location"] == f"/login/?next={path}"
    assert not get_user(dani_browser).is_authenticated


def test_a_reset_leaves_everyone_else_and_their_sessions_alone(admin, voters):
    ada_browser = signed_in(voters["ada"])

    reset(admin, voters["Dani"])

    assert ada_browser.get("/").status_code == 200
    assert stored(voters["ada"])[1] is False
    assert voters["ada"].check_password(PASSWORD)


def test_the_old_password_no_longer_signs_in(admin, voters):
    reset(admin, voters["Dani"])

    assert not Client().login(username="Dani", password=PASSWORD)
