"""The runtime box on the Films tab's rows: the admin's runtime edit in every phase, saved apart from Approve (#28, #97)."""

import html
import re
from unittest import mock

import pytest

from ribcage.console import films
from ribcage.films.film import RuntimeSource
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions import runtime
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.suggestions.withdrawal import withdraw
from tests.films import CABINET_OF_CURIOSITIES, a_tmdb_film
from tests.http.test_approve_and_drop import acts
from tests.http.test_films_tab import TAB, suggested
from tests.http.test_phase import walk_to
from tests.http.test_roster_tab import text

EDIT = "/console/films/runtime/"
UNDECIDED, APPROVED, DROPPED = Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED
ON_THE_BALLOT = "A film on the ballot needs a runtime. Type its length in minutes, like 144."


def edit(admin, suggestion, typed, show=None):
    fields = {"suggestion": suggestion.pk, "runtime": typed}
    return admin.post(EDIT, fields | ({"show": show} if show is not None else {}))


def stored(suggestion):
    found = Suggestion.objects.get(pk=suggestion.pk)
    return found.runtime, found.tmdb_runtime


def box(page, suggestion):
    """The row's runtime cell: where its form posts and lands, its fields, the box's value, and the cell's words."""
    cell = re.search(rf'data-keeps-place="{suggestion.pk}">.*?<td class="films-ledger__runtime">(.*?)</td>', page, re.S)[1]
    form = re.search(r'<form method="post" action="([^"]+)" class="runtime-box" data-lands-on="([^"]+)">(.*?)</form>', cell, re.S)
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', form[3]))
    fields.pop("csrfmiddlewaretoken")
    value = html.unescape(re.search(r'<input type="text" name="runtime" value="([^"]*)"', form[3])[1])
    return form[1], html.unescape(form[2]), fields, value, text(cell)


def approve_offered(page, suggestion):
    *_, buttons = acts(page, suggestion)
    return buttons[0][2]


@pytest.fixture
def cube(voters):
    walk_to(Phase.APPROVE)
    return suggested(voters["Hanna"], "Cube", runtime=90)


# Saving


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("approval", [UNDECIDED, APPROVED, DROPPED])
def test_an_edit_saves_in_every_phase_leaving_tmdbs_runtime_unchanged(admin, voters, phase, approval):
    suggestion = suggested(voters["Hanna"], "Cube", approval, runtime=90)
    walk_to(phase)

    response = edit(admin, suggestion, " 94 ")

    assert response.status_code == 302
    assert stored(suggestion) == (94, 90)
    assert Suggestion.objects.get(pk=suggestion.pk).runtime_source is RuntimeSource.HAND_ENTERED


def test_the_box_holds_the_runtime_and_reads_by_hand_once_edited(admin, cube):
    assert box(admin.get(TAB).text, cube)[3:] == ("90", "TMDB Save")

    edit(admin, cube, "94")

    assert box(admin.get(TAB).text, cube)[3:] == ("94", "by hand ⚠ TMDB says 90 Save")


def test_the_summary_counts_the_edited_runtime_on_the_ballot(admin, voters):
    walk_to(Phase.VOTE)
    suggestion = suggested(voters["ada"], "Short", APPROVED, runtime=47)

    edit(admin, suggestion, "52")

    assert "On the ballot: 1 film · 52 min screen time" in text(admin.get(TAB).text)


@pytest.mark.parametrize("cap", [str(runtime.LONGEST), "0" * 40 + "1"])
def test_the_box_takes_up_to_the_fields_cap(admin, cube, cap):
    edit(admin, cube, cap)

    assert stored(cube) == (int(cap), 90)


# The differs flag


@pytest.mark.parametrize(("typed", "flag"), [("90", None), ("91", "⚠ TMDB says 90"), ("89", "⚠ TMDB says 90"), ("", "⚠ TMDB says 90")])
def test_the_differs_flag_follows_the_runtime_and_tmdbs(admin, cube, typed, flag):
    edit(admin, cube, typed)

    words = box(admin.get(TAB).text, cube)[4]

    assert ("⚠ TMDB says" in words) is (flag is not None)
    if flag:
        assert flag in words


def test_correcting_back_to_tmdbs_runtime_reads_tmdb_again_with_no_flag(admin, cube):
    edit(admin, cube, "94")
    edit(admin, cube, "90")

    assert box(admin.get(TAB).text, cube)[3:] == ("90", "TMDB Save")


@pytest.mark.parametrize("typed", ["47", "60", ""])
def test_a_hand_entered_film_never_shows_the_flag(admin, voters, typed):
    walk_to(Phase.APPROVE)
    cabinet = Suggestion.objects.suggest(voters["ada"], CABINET_OF_CURIOSITIES, "Pitch.")

    edit(admin, cabinet, typed)

    assert "TMDB says" not in admin.get(TAB).text


@pytest.mark.parametrize("typed", ["120", ""])
def test_a_tmdb_film_tmdb_gave_no_runtime_never_shows_the_flag(admin, voters, typed):
    walk_to(Phase.APPROVE)
    untimed = Suggestion.objects.suggest(voters["ada"], a_tmdb_film(77, "Untimed", None), "Pitch.", runtime=100)

    edit(admin, untimed, typed)

    assert stored(untimed) == (int(typed) if typed else None, None)
    assert "TMDB says" not in admin.get(TAB).text


# Clearing


@pytest.mark.parametrize("approval", [UNDECIDED, DROPPED])
@pytest.mark.parametrize("cleared", ["", "   "])
def test_clearing_an_unapproved_films_runtime_saves_it_empty_and_makes_approve_unavailable(admin, voters, approval, cleared):
    walk_to(Phase.APPROVE)
    suggestion = suggested(voters["Hanna"], "Cube", approval, runtime=90)
    show = {"show": "dropped"} if approval == DROPPED else {}

    response = edit(admin, suggestion, cleared)
    page = admin.get(TAB, show).text

    assert response.status_code == 302
    assert stored(suggestion) == (None, 90)
    assert box(page, suggestion)[3:] == ("", "required to approve ⚠ TMDB says 90 Save")
    assert '<span class="runtime-box__required">required to approve</span>' in page
    assert approve_offered(page, suggestion) is False


def test_a_cleared_film_cannot_be_approved_until_it_has_a_runtime_again(admin, cube):
    edit(admin, cube, "")
    admin.post("/console/films/approval/", {"suggestion": cube.pk, "from_approval": UNDECIDED, "to_approval": APPROVED})
    assert Suggestion.objects.get(pk=cube.pk).approval == UNDECIDED

    edit(admin, cube, "90")

    assert approve_offered(admin.get(TAB).text, cube) is True


@pytest.mark.parametrize("cleared", ["", "  "])
def test_clearing_an_approved_films_runtime_is_refused(admin, voters, cleared):
    walk_to(Phase.VOTE)
    suggestion = suggested(voters["Hanna"], "Cube", APPROVED, runtime=94)

    response = edit(admin, suggestion, cleared, "approved")

    assert response.status_code == 200
    assert stored(suggestion) == (94, 94)
    _, _, _, value, words = box(response.text, suggestion)
    assert value == cleared
    assert ON_THE_BALLOT in words
    assert Suggestion.objects.get(pk=suggestion.pk).approval == APPROVED


# Refusals


@pytest.mark.parametrize(("typed", "says"), [
    ("abc", runtime.NOT_WHOLE_MINUTES),
    ("1h 30", runtime.NOT_WHOLE_MINUTES),
    ("144 min", runtime.NOT_WHOLE_MINUTES),
    ("90.5", runtime.NOT_WHOLE_MINUTES),
    ("-5", runtime.NOT_POSITIVE),
    ("0", runtime.NOT_POSITIVE),
    (str(runtime.LONGEST + 1), runtime.TOO_LONG),
    ("9" * 400, runtime.TOO_LONG),
])
def test_a_value_that_isnt_positive_whole_minutes_is_refused_with_minutes_line_keeping_the_typed_value(admin, cube, typed, says):
    response = edit(admin, cube, typed)

    assert response.status_code == 200
    assert stored(cube) == (90, 90)
    _, _, _, value, words = box(response.text, cube)
    assert value == typed
    assert words == f"Save {says}"
    assert f'aria-describedby="runtime-refusal-{cube.pk}" autofocus>' in response.text


def test_a_refusal_keeps_the_other_rows_as_they_are(admin, voters, cube):
    other = suggested(voters["ada"], "Pulse", runtime=119)

    response = edit(admin, cube, "abc")

    assert box(response.text, other)[3:] == ("119", "TMDB Save")
    assert response.text.count('aria-describedby="runtime-refusal-') == 1


@pytest.mark.parametrize(("show", "lands_on"), [
    (None, TAB),
    ("all", TAB),
    ("undecided", f"{TAB}?show=undecided"),
    ("dropped", f"{TAB}?show=dropped"),
    ("nonsense", TAB),
])
def test_a_save_reloads_onto_the_filter_it_was_sent_from(admin, cube, show, lands_on):
    response = edit(admin, cube, "95", show)

    assert response.status_code == 302
    assert response.url == lands_on


def test_a_refusal_renders_the_tab_under_the_filter_it_was_sent_from(admin, voters, cube):
    suggested(voters["ada"], "Pulse", APPROVED, runtime=119)

    page = edit(admin, cube, "abc", "undecided").text

    assert "Cube" in page and "Pulse" not in page.split("<table", 1)[1]
    assert re.search(r'<a href="/console/films/\?show=undecided" aria-current="page">', page)
    assert box(page, cube)[1] == f"{TAB}?show=undecided"
    assert box(page, cube)[2]["show"] == "undecided"
    assert re.search(r'<a href="/console/films/"[^>]*aria-current="page"', page)


@pytest.mark.parametrize(("show", "lands_on"), [(None, TAB), ("undecided", f"{TAB}?show=undecided")])
def test_each_box_posts_here_naming_its_filter_and_lands_back_on_it(admin, cube, show, lands_on):
    action, form_lands_on, fields, _, _ = box(admin.get(TAB, {"show": show} if show else {}).text, cube)

    assert action == EDIT
    assert fields["suggestion"] == str(cube.pk)
    assert form_lands_on == lands_on
    assert edit(admin, cube, "91", fields["show"]).url == lands_on


def test_the_box_sits_in_its_row_inside_the_tabs_kept_scroll_region(admin, cube):
    page = admin.get(TAB).text

    assert re.search(rf'<div class="films-ledger__frame" data-keeps-scroll>.*data-keeps-place="{cube.pk}">.*?action="{EDIT}"', page, re.S)


# What changes nothing


@pytest.mark.parametrize("named", ["", "abc", "999999"])
def test_a_post_naming_no_suggestion_changes_nothing_and_reloads(admin, cube, named):
    response = admin.post(EDIT, {"suggestion": named, "runtime": "95", "show": "undecided"})

    assert response.url == f"{TAB}?show=undecided"
    assert stored(cube) == (90, 90)


def test_a_suggestion_withdrawn_since_changes_nothing_and_reloads(admin, cube):
    named = cube.pk
    withdraw(cube)

    response = admin.post(EDIT, {"suggestion": named, "runtime": "abc", "show": "undecided"})

    assert response.url == f"{TAB}?show=undecided"
    assert not Suggestion.objects.exists()


def test_a_get_saves_nothing_and_lands_on_the_tab(admin, cube):
    response = admin.get(EDIT, {"suggestion": cube.pk, "runtime": "95"})

    assert response.status_code == 302
    assert response.url == TAB
    assert stored(cube) == (90, 90)


def test_a_voter_cannot_edit_here(client, voters, cube):
    client.force_login(voters["Hanna"])

    edit(client, cube, "95")

    assert stored(cube) == (90, 90)


# Another request landing between the read and the write

def test_a_withdraw_between_the_read_and_the_save_changes_nothing(admin, cube):
    real = runtime.correct

    def withdrawn_first(found, typed):
        Suggestion.objects.filter(pk=found.pk).delete()
        return real(found, typed)

    with mock.patch.object(films, "correct", withdrawn_first):
        assert edit(admin, cube, "95").status_code == 302

    assert not Suggestion.objects.filter(pk=cube.pk).exists()


def test_a_clear_between_approves_read_and_update_changes_nothing(admin, cube):
    real = films.may_approve

    def cleared_first(minutes):
        Suggestion.objects.filter(pk=cube.pk).update(runtime=None)
        return real(minutes)

    with mock.patch.object(films, "may_approve", cleared_first):
        acts_post = admin.post("/console/films/approval/", {"suggestion": cube.pk, "from_approval": "undecided", "to_approval": "approved"})

    assert acts_post.status_code == 302
    assert Suggestion.objects.get(pk=cube.pk).approval == UNDECIDED


def test_an_approve_between_the_clears_read_and_update_keeps_the_runtime(admin, cube):
    real = films.withdrawable

    def approved_first(suggestion):
        Suggestion.objects.filter(pk=cube.pk).update(approval=APPROVED)
        return real(suggestion)

    with mock.patch.object(films, "withdrawable", approved_first):
        refused = edit(admin, cube, "")

    assert refused.status_code == 200
    assert ON_THE_BALLOT in box(refused.text, cube)[4]
    assert Suggestion.objects.get(pk=cube.pk).approval == APPROVED
    assert stored(cube)[0] is not None


def test_clearing_is_refused_exactly_where_withdrawable_says_something_holds_the_film(admin, voters):
    walk_to(Phase.APPROVE)
    held = suggested(voters["Hanna"], "Cube", DROPPED, runtime=90)
    free = suggested(voters["Hanna"], "Rope", DROPPED, runtime=80)

    # A later milestone's hold on a dropped film; the clear follows `withdrawable` (#97, the dev, 2026-10-24).
    with mock.patch.object(films, "withdrawable", lambda suggestion: suggestion.pk != held.pk):
        refused = edit(admin, held, "")
        cleared = edit(admin, free, "")

    assert refused.status_code == 200
    assert ON_THE_BALLOT in box(refused.text, held)[4]
    assert stored(held) == (90, 90)
    assert cleared.status_code == 302
    assert stored(free) == (None, 80)
