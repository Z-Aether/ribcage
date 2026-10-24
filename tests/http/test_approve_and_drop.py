"""Approve and Drop on the Films tab's rows: instant, never phase-gated, and refused when stale (#15, #28, #96)."""

import html
import re

import pytest

from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.withdrawal import withdraw
from tests.films import a_tmdb_film
from tests.http.test_films_tab import TAB, suggested
from tests.http.test_phase import walk_to
from tests.http.test_pool import main

DECIDE = "/console/films/approval/"
UNDECIDED, APPROVED, DROPPED = Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED
# Every change a row offers; nothing returns a film to undecided (#61, 2026-10-22).
DECISIONS = [(UNDECIDED, APPROVED), (UNDECIDED, DROPPED), (APPROVED, DROPPED), (DROPPED, APPROVED)]


def decide(admin, suggestion, from_approval, to_approval, show=None):
    fields = {"suggestion": suggestion.pk, "from_approval": from_approval, "to_approval": to_approval}
    return admin.post(DECIDE, fields | ({"show": show} if show is not None else {}))


def approval_of(suggestion):
    return Suggestion.objects.get(pk=suggestion.pk).approval


def acts(page, suggestion):
    """The row's form: where it posts, the page it lands on, its fields, and each act with whether it is offered."""
    row = re.search(rf'<tr data-suggestion="{suggestion.pk}" data-ledger-row data-keeps-place="{suggestion.pk}">(.*?)</tr>', page, re.S)[1]
    form = re.search(r'<form method="post" action="([^"]+)" data-lands-on="([^"]+)">(.*?)</form>', row, re.S)
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', form[3]))
    fields.pop("csrfmiddlewaretoken")
    buttons = re.findall(r'<button type="submit" class="button--quiet" name="to_approval" value="(\w+)"( disabled)?>(\w+)</button>', form[3])
    return form[1], html.unescape(form[2]), fields, [(label, value, not disabled) for value, disabled, label in buttons]


@pytest.fixture
def cube(voters):
    walk_to(Phase.APPROVE)
    return suggested(voters["Hanna"], "Cube", runtime=90)


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize(("before", "after"), DECISIONS)
def test_approve_and_drop_work_in_every_phase(admin, voters, phase, before, after):
    suggestion = suggested(voters["Hanna"], "Cube", before)
    walk_to(phase)

    response = decide(admin, suggestion, before, after)

    assert response.status_code == 302
    assert approval_of(suggestion) == after


@pytest.mark.parametrize(("show", "lands_on"), [
    (None, TAB),
    ("all", TAB),
    ("undecided", f"{TAB}?show=undecided"),
    ("approved", f"{TAB}?show=approved"),
    ("dropped", f"{TAB}?show=dropped"),
    ("nonsense", TAB),
])
def test_a_decision_reloads_onto_the_filter_it_was_sent_from_with_no_message(admin, cube, show, lands_on):
    response = decide(admin, cube, UNDECIDED, APPROVED, show)

    assert response.status_code == 302
    assert response.url == lands_on
    assert admin.get(response.url).text.count("Cube") == admin.get(lands_on).text.count("Cube")


@pytest.mark.parametrize("approval", [UNDECIDED, DROPPED])
def test_approving_a_film_with_no_runtime_is_refused_and_writes_nothing(admin, voters, approval):
    walk_to(Phase.APPROVE)
    untimed = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(77, "Untimed", None), "Pitch.")
    Suggestion.objects.filter(pk=untimed.pk).update(approval=approval)

    response = decide(admin, untimed, approval, APPROVED)

    assert response.status_code == 302
    assert approval_of(untimed) == approval


@pytest.mark.parametrize(("named", "actual", "to"), [
    # A double click: the second post names the approval the first one changed.
    (UNDECIDED, APPROVED, APPROVED),
    (UNDECIDED, DROPPED, DROPPED),
    # A stale tab: another tab decided since this one loaded.
    (UNDECIDED, DROPPED, APPROVED),
    (APPROVED, DROPPED, DROPPED),
    (DROPPED, UNDECIDED, APPROVED),
    (APPROVED, UNDECIDED, DROPPED),
])
def test_a_stale_post_changes_nothing(admin, voters, named, actual, to):
    walk_to(Phase.APPROVE)
    suggestion = suggested(voters["Hanna"], "Cube", actual)

    response = decide(admin, suggestion, named, to)

    assert response.status_code == 302
    assert approval_of(suggestion) == actual


@pytest.mark.parametrize(("before", "to"), [(APPROVED, UNDECIDED), (DROPPED, UNDECIDED), (APPROVED, "removed"), (APPROVED, APPROVED)])
def test_nothing_returns_a_film_to_undecided_or_names_no_decision(admin, voters, before, to):
    walk_to(Phase.APPROVE)
    suggestion = suggested(voters["Hanna"], "Cube", before)

    decide(admin, suggestion, before, to)

    assert approval_of(suggestion) == before


@pytest.mark.parametrize("named", ["", "abc", "999999"])
def test_a_post_naming_no_suggestion_changes_nothing_and_reloads(admin, cube, named):
    response = admin.post(DECIDE, {"suggestion": named, "from_approval": UNDECIDED, "to_approval": APPROVED, "show": "undecided"})

    assert response.url == f"{TAB}?show=undecided"
    assert approval_of(cube) == UNDECIDED


def test_a_suggestion_withdrawn_since_changes_nothing_and_the_reload_shows_it_gone(admin, cube):
    named = cube.pk
    withdraw(cube)

    response = admin.post(DECIDE, {"suggestion": named, "from_approval": UNDECIDED, "to_approval": APPROVED, "show": "undecided"})

    assert response.url == f"{TAB}?show=undecided"
    assert not Suggestion.objects.exists()
    assert "Cube" not in admin.get(response.url).text


def test_a_get_decides_nothing(admin, cube):
    response = admin.get(DECIDE, {"suggestion": cube.pk, "from_approval": UNDECIDED, "to_approval": APPROVED})

    assert response.status_code == 405
    assert approval_of(cube) == UNDECIDED


def test_a_voter_cannot_decide(client, voters, cube):
    client.force_login(voters["Hanna"])

    decide(client, cube, UNDECIDED, APPROVED)

    assert approval_of(cube) == UNDECIDED


# The row's acts


@pytest.mark.parametrize(("approval", "offered"), [
    (UNDECIDED, [("Approve", "approved", True), ("Drop", "dropped", True)]),
    (APPROVED, [("Approve", "approved", False), ("Drop", "dropped", True)]),
    (DROPPED, [("Approve", "approved", True), ("Drop", "dropped", False)]),
])
def test_each_row_offers_the_acts_that_change_its_approval(admin, voters, approval, offered):
    walk_to(Phase.APPROVE)
    suggestion = suggested(voters["Hanna"], "Cube", approval)

    action, lands_on, fields, buttons = acts(admin.get(TAB, {"show": "dropped"} if approval == DROPPED else {}).text, suggestion)

    assert action == DECIDE
    assert fields["suggestion"] == str(suggestion.pk)
    assert fields["from_approval"] == approval
    assert buttons == offered


@pytest.mark.parametrize("approval", [UNDECIDED, DROPPED])
def test_approve_is_unavailable_on_a_row_with_no_runtime(admin, voters, approval):
    walk_to(Phase.APPROVE)
    suggestion = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(77, "Untimed", None), "Pitch.")
    Suggestion.objects.filter(pk=suggestion.pk).update(approval=approval)

    *_, buttons = acts(admin.get(TAB).text, suggestion)

    assert buttons[0] == ("Approve", "approved", False)
    assert buttons[1][2] is (approval != DROPPED)


@pytest.mark.parametrize(("show", "lands_on"), [
    (None, TAB),
    ("undecided", f"{TAB}?show=undecided"),
])
def test_a_rows_form_names_the_filter_it_was_sent_from_and_lands_back_on_it(admin, cube, show, lands_on):
    _, form_lands_on, fields, _ = acts(admin.get(TAB, {"show": show} if show else {}).text, cube)

    assert form_lands_on == lands_on
    assert decide(admin, cube, UNDECIDED, DROPPED, fields["show"]).url == lands_on


def test_the_rows_acts_sit_in_the_tabs_kept_scroll_region(admin, cube):
    page = admin.get(TAB).text

    assert re.search(rf'<div class="films-ledger__frame" data-keeps-scroll>.*action="{DECIDE}"', page, re.S)


def test_each_row_names_its_place_so_a_decision_lands_with_it_where_it_was_on_screen(admin, cube):
    page = admin.get(TAB).text

    assert re.search(rf'<tr data-suggestion="{cube.pk}" data-ledger-row data-keeps-place="{cube.pk}">.*?action="{DECIDE}"', page, re.S)


def test_the_opened_card_spans_every_column(admin, cube):
    page = admin.get(TAB).text

    columns = len(re.findall(r'<th scope="col"', re.search(r"<thead>(.*?)</thead>", page, re.S)[1]))
    assert f'<tr class="ledger__detail" id="film-{cube.pk}" hidden>\n                <td colspan="{columns}">' in page


# What voters see


def pencil_and_withdraw_removed(page, suggestion):
    page = re.sub(rf' <a class="runtime__pencil" id="runtime-{suggestion.pk}"[^>]*>✎</a>', "", page)
    return re.sub(rf'<div class="withdraw" data-withdraw>(?:(?!</div>).)*?id="withdraw-{suggestion.pk}".*?</div>', "", page, flags=re.S)


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE])
def test_voters_see_no_mark_of_a_decision_but_an_approved_films_missing_pencil_and_withdraw_in_suggest(admin, voters, phase):
    # The suggester's own view, so Withdraw is on the card while nothing holds the film.
    hanna = voters["Hanna"]
    approved, dropped, after_drop = (suggested(hanna, title) for title in ["Cube", "Pulse", "Possession"])
    walk_to(phase)
    admin.force_login(hanna)
    undecided = main(admin.get("/").text)
    if phase is Phase.SUGGEST:
        assert f'id="withdraw-{approved.pk}"' in undecided and f'id="runtime-{approved.pk}"' in undecided

    decide(admin, approved, UNDECIDED, APPROVED)
    decide(admin, dropped, UNDECIDED, DROPPED)
    decide(admin, after_drop, UNDECIDED, DROPPED)
    decide(admin, after_drop, DROPPED, APPROVED)
    decide(admin, after_drop, APPROVED, DROPPED)
    decided = main(admin.get("/").text)

    assert [approval_of(each) for each in (approved, dropped, after_drop)] == [APPROVED, DROPPED, DROPPED]
    expected = pencil_and_withdraw_removed(undecided, approved) if phase is Phase.SUGGEST else undecided
    # Spacing aside, as the bar's template leaves Withdraw's line behind it.
    assert decided.split() == expected.split()
    assert not re.search(r"approved|dropped|undecided|ballot", decided, re.I)
