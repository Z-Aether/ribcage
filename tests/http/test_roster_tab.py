import html
import re

import pytest
from django.contrib.auth import get_user
from django.test import Client

from ribcage.identity.models import Voter
from ribcage.identity.removal import remove
from tests.http.signing_in import PASSWORD
from tests.http.test_registration import register

TAB = "/console/roster/"
REMOVE = "/console/roster/remove/"


# Cancel at the size of the arm it replaces, whose label it keeps hidden (#85).
CANCEL = r'<a class="button button--quiet console-cancel" href="([^"]+)"><span>Cancel</span><span class="console-cancel__keep" aria-hidden="true">([^<]+)</span></a>'


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def rows(page):
    """Each voter's row on the tab: their id, the name shown and the row's cells as text."""
    found = re.findall(r'<tr data-voter="(\d+)"[^>]*>\s*<td class="roster__name">(.*?)</td>(.*?)</tr>', page, re.S)
    return [(int(pk), html.unescape(name), text(rest)) for pk, name, rest in found]


def act_links(page, label):
    """Where each row's link labelled `label` points, such as Remove… or Reset password…."""
    return [html.unescape(href) for href in re.findall(rf'<a class="button button--quiet" href="([^"]+)">{label}</a>', page)]


def confirm(page):
    """The armed act's confirm: where it posts, its fields, the act its button names, Cancel's address and the text above them."""
    form = re.search(r'<form method="post" action="([^"]+)" class="roster-confirm">(.*?)</form>', page, re.S)
    if form is None:
        return None
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]+)">', form[2]))
    fields.pop("csrfmiddlewaretoken")
    act = html.unescape(re.search(r'<p class="console-confirm"><button type="submit">([^<]+)</button></p>', form[2])[1])
    cancel = re.search(CANCEL, page)[1]
    said = text(re.sub(r'<p class="console-confirm">.*?</p>', "", form[2], flags=re.S))
    return form[1], fields, act, cancel, said


def actions(page, voter):
    """What stands in each place in `voter`'s actions cell: ("arm", label), ("cancel", the arm it stands for) or ("kept", an empty arm's place)."""
    cell = re.search(rf'<tr data-voter="{voter.pk}"[^>]*>.*?<td class="roster__actions">(.*?)</td>', page, re.S)[1]
    found = re.findall(rf'<a class="button button--quiet" href="[^"]+">([^<]+)</a>|{CANCEL}|<a class="button button--quiet console-kept" aria-hidden="true">([^<]+)</a>', cell)
    return [("arm", arm) if arm else ("cancel", stands_for) if stands_for else ("kept", kept) for arm, _, stands_for, kept in found]


def signed_in(voter, password=PASSWORD):
    browser = Client()
    assert browser.login(username=voter.display_name, password=password)
    return browser


def test_the_roster_lists_every_voter_one_row_each_by_name_regardless_of_case(admin, voters):
    shown = rows(admin.get(TAB).text)

    assert [(pk, name) for pk, name, _ in shown] == [(voters[name].pk, name) for name in ["ada", "Dani", "Hanna"]]


def test_a_name_is_shown_as_typed_and_escaped(admin, db):
    Voter.objects.create_voter("<b>Zoë</b>")

    page = admin.get(TAB).text

    assert [name for _, name, _ in rows(page)] == ["<b>Zoë</b>"]
    assert "<b>Zoë</b>" not in page


def test_an_empty_roster_says_nobody_has_registered(admin):
    page = admin.get(TAB).text

    assert rows(page) == []
    assert "Nobody has registered yet." in text(page)


def test_every_row_offers_removal_armed_by_a_link_to_the_tab(admin, voters):
    page = admin.get(TAB).text

    assert act_links(page, "Remove…") == [f"{TAB}?remove={voters[name].pk}" for name in ["ada", "Dani", "Hanna"]]
    assert confirm(page) is None


def test_arming_removal_deletes_nothing_and_prints_the_confirm_under_the_voters_row(admin, voters):
    dani = voters["Dani"]
    before = list(Voter.objects.order_by("pk").values_list("pk", "display_name", "password"))
    dani_browser = signed_in(dani)

    page = admin.get(TAB, {"remove": dani.pk}).text

    assert list(Voter.objects.order_by("pk").values_list("pk", "display_name", "password")) == before
    assert get_user(dani_browser).pk == dani.pk
    action, fields, act, cancel, _ = confirm(page)
    assert (action, fields, act, cancel) == (REMOVE, {"voter": str(dani.pk)}, "Remove Dani", TAB)
    assert re.search(rf'<tr data-voter="{dani.pk}" class="is-armed">.*?</tr>\s*<tr class="ledger__detail">\s*<td colspan="5">\s*<form', page, re.S)


def test_the_confirm_lists_what_goes_and_says_the_join_code_still_lets_them_back(admin, voters):
    page = admin.get(TAB, {"remove": voters["Dani"].pk}).text

    *_, said = confirm(page)
    goes = [text(item) for item in re.findall(r'<li class="roster-confirm__goes">(.*?)</li>', page, re.S)]
    assert said.startswith("Removing Dani takes away: ")
    assert goes == ["their display name and password", "their sessions, so they are signed out everywhere"]
    assert said.endswith("Removal is not a ban: the join code still lets them register again.")


def test_the_armed_row_gives_up_its_arm_and_the_others_keep_theirs(admin, voters):
    page = admin.get(TAB, {"remove": voters["Dani"].pk}).text

    assert act_links(page, "Remove…") == [f"{TAB}?remove={voters[name].pk}" for name in ["ada", "Hanna"]]


def test_armed_removal_puts_cancel_in_the_remove_arms_place_and_its_confirm_in_the_row_below(admin, voters):
    page = admin.get(TAB, {"remove": voters["Dani"].pk}).text

    assert actions(page, voters["ada"]) == [("arm", "Reset password…"), ("arm", "Remove…")]
    assert actions(page, voters["Dani"]) == [("kept", "Reset password…"), ("cancel", "Remove…")]
    armed_row = re.search(rf'<tr data-voter="{voters["Dani"].pk}" class="is-armed">(.*?)</tr>', page, re.S)[1]
    assert "<button" not in armed_row


@pytest.mark.parametrize("arm", ["", "x", "-1", "1.0", "99999999999999999999999"])
def test_an_arm_for_no_voter_arms_nothing(admin, voters, arm):
    response = admin.get(TAB, {"remove": arm})

    assert response.status_code == 200
    assert confirm(response.text) is None
    assert len(act_links(response.text, "Remove…")) == 3


def test_an_arm_for_a_voter_already_removed_arms_nothing(admin, voters):
    gone = voters["Dani"].pk
    remove(voters["Dani"])

    page = admin.get(TAB, {"remove": gone}).text

    assert confirm(page) is None
    assert [name for _, name, _ in rows(page)] == ["ada", "Hanna"]


def test_confirming_removes_the_voter_and_reloads_the_tab_without_them(admin, voters):
    action, fields, *_ = confirm(admin.get(TAB, {"remove": voters["Dani"].pk}).text)

    response = admin.post(action, fields, follow=True)

    assert response.redirect_chain == [(TAB, 302)]
    assert [name for _, name, _ in rows(response.text)] == ["ada", "Hanna"]
    assert not Voter.objects.filter(pk=voters["Dani"].pk).exists()


@pytest.mark.parametrize("path", ["/", "/how-it-works/", "/password/", "/gallery/"])
def test_a_removed_voters_session_then_reaches_only_login(admin, voters, path):
    dani_browser = signed_in(voters["Dani"])

    admin.post(REMOVE, {"voter": voters["Dani"].pk})

    response = dani_browser.get(path, follow=True)
    assert response.redirect_chain == [(f"/login/?next={path}", 302)]
    assert response.status_code == 200
    assert not get_user(dani_browser).is_authenticated


def test_a_removed_voters_stale_post_and_log_out_land_on_login(admin, voters):
    dani_browser = signed_in(voters["Dani"])
    admin.post(REMOVE, {"voter": voters["Dani"].pk})

    assert dani_browser.post("/password/", {}).headers["Location"] == "/login/?next=/password/"
    assert dani_browser.post("/logout/").headers["Location"] == "/login/"


def test_removal_leaves_everyone_else_and_their_sessions_alone(admin, voters):
    ada_browser = signed_in(voters["ada"])

    admin.post(REMOVE, {"voter": voters["Dani"].pk})

    assert sorted(Voter.objects.values_list("display_name", flat=True)) == ["Hanna", "ada"]
    assert get_user(ada_browser).pk == voters["ada"].pk
    assert ada_browser.get("/").status_code == 200


@pytest.mark.parametrize("typed", ["Dani", "DANI", "dani"])
def test_a_removed_voters_display_name_can_register_again_with_the_join_code(admin, voters, typed):
    admin.post(REMOVE, {"voter": voters["Dani"].pk})
    newcomer = Client()

    response = register(newcomer, typed)

    assert response.headers["Location"] == "/how-it-works/"
    assert Voter.objects.get(display_name=typed).pk != voters["Dani"].pk
    assert get_user(newcomer).display_name == typed


def test_a_removed_voters_old_session_does_not_sign_in_as_whoever_registers_their_name_again(admin, voters):
    dani_browser = signed_in(voters["Dani"])
    admin.post(REMOVE, {"voter": voters["Dani"].pk})
    register(Client(), "Dani")

    assert not get_user(dani_browser).is_authenticated


def test_a_confirm_for_a_voter_already_removed_removes_nobody_and_reloads_the_tab(admin, voters):
    action, fields, *_ = confirm(admin.get(TAB, {"remove": voters["Dani"].pk}).text)
    admin.post(action, fields)

    response = admin.post(action, fields)

    assert (response.status_code, response.headers["Location"]) == (302, TAB)
    assert Voter.objects.count() == 2


@pytest.mark.parametrize("fields", [{}, {"voter": ""}, {"voter": "x"}, {"voter": "99999999999999999999999"}])
def test_a_confirm_that_names_no_voter_removes_nobody_and_reloads_the_tab(admin, voters, fields):
    response = admin.post(REMOVE, fields)

    assert (response.status_code, response.headers["Location"]) == (302, TAB)
    assert Voter.objects.count() == 3


def test_the_remove_route_answers_post_alone(admin):
    assert admin.get(REMOVE).status_code == 405


def test_removal_is_one_routine_that_deletes_the_voters_row(voters):
    remove(voters["Dani"])

    assert sorted(Voter.objects.values_list("display_name", flat=True)) == ["Hanna", "ada"]
