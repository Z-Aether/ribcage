import html
import re
from datetime import datetime

import pytest
from django.templatetags.static import static

from ribcage.identity.models import Voter
from ribcage.phase.history import current, move
from ribcage.phase.order import PHASES, Phase, neighbours
from ribcage.suggestions.models import Approval, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_phase import PAGE_HEADINGS, history, walk_to
from tests.http.test_roster_tab import CANCEL

SUGGEST, APPROVE, VOTE, PICK, RUN = Phase
TAB = "/console/phase/"
MOVE = "/console/phase/move/"

# Each move's confirm button names the act, not the destination (#28).
ACTS = {
    (SUGGEST, APPROVE): "Close suggestions",
    (APPROVE, SUGGEST): "Reopen suggestions",
    (APPROVE, VOTE): "Open the ballot",
    (VOTE, APPROVE): "Close the ballot",
    (VOTE, PICK): "Close VOTE and open the scores",
    (PICK, VOTE): "Reopen VOTE",
    (PICK, RUN): "Publish the plan",
    (RUN, PICK): "Unpublish",
}
EVERY_MOVE = list(ACTS)


def phases(page):
    """Each phase on the tab, whether it is marked current, and the date it was last entered, if any."""
    found = re.findall(
        r'<li class="phase-list__phase"( aria-current="step")?>\s*<span class="phase-list__name">(\w+)</span>\s*(?:<time datetime="([^"]+)">)?',
        page,
    )
    return [(name, bool(marked), datetime.fromisoformat(entered) if entered else None) for marked, name, entered in found]


def moves(page):
    return dict(re.findall(r'<section class="phase-move phase-move--\w+(?: phase-move--irreversible)?(?: is-armed)?" data-to="(\w+)">(.*?)</section>', page, re.S))


def text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def heading(fragment):
    return text(re.search(r"<h2>(.*?)</h2>", fragment, re.S)[1])


def head(fragment):
    """The move's top line, its heading and the arm or the Cancel that stands in the arm's place."""
    return re.search(r'<div class="phase-move__head">(.*?)</div>', fragment, re.S)[1]


def arm_link(fragment):
    found = re.search(r'<a class="button button--quiet" href="([^"]+)">([^<]+)</a>', head(fragment))
    return found and (html.unescape(found[1]), html.unescape(found[2]))


def cancel_link(fragment):
    """Where the Cancel in the arm's place leads, and the arm whose label it keeps hidden to keep the arm's size (#85)."""
    found = re.search(CANCEL, head(fragment))
    return found and (found[1], html.unescape(found[2]))


def confirm(fragment):
    """The armed move's form: where it posts, its fields and the act its button names, or None while unarmed."""
    form = re.search(r'<form method="post" action="([^"]+)">(.*?)</form>', fragment, re.S)
    if form is None:
        return None
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]+)">', form[2]))
    fields.pop("csrfmiddlewaretoken")
    act = re.search(r'<p class="console-confirm"><button type="submit"[^>]*>([^<]+)</button></p>', form[2])[1]
    return form[1], fields, html.unescape(act), cancel_link(fragment)[0]


def armed(admin, from_phase, to_phase):
    return admin.get(TAB, {"from": from_phase, "arm": to_phase}).text


@pytest.mark.parametrize("phase", PHASES)
def test_the_tab_shows_the_five_phases_in_order_marking_the_current_one(admin, phase):
    walk_to(phase)

    shown = phases(admin.get(TAB).text)

    assert [(name, marked) for name, marked, _ in shown] == [(each, each == phase) for each in PHASES]


def test_on_a_fresh_database_no_phase_has_a_date_not_even_suggest(admin):
    assert [entered for _, _, entered in phases(admin.get(TAB).text)] == [None] * 5


def test_the_dates_follow_the_history(admin, clock):
    entered = {}
    for before, after in [(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, PICK), (PICK, VOTE), (VOTE, APPROVE), (APPROVE, SUGGEST)]:
        clock.advance(hours=7)
        move(before, after)
        entered[after] = clock.now

    shown = phases(admin.get(TAB).text)

    assert [(name, date) for name, _, date in shown] == [(each, entered.get(each)) for each in PHASES]


def test_each_date_is_shown_as_a_day_and_a_time(admin, clock, settings):
    settings.TIME_ZONE = "Europe/Budapest"
    clock.now = datetime.fromisoformat("2026-10-31T17:05:00+00:00")
    move(SUGGEST, APPROVE)

    assert '<time datetime="2026-10-31T18:05:00+01:00">Sat 31 Oct, 18:05</time>' in admin.get(TAB).text


@pytest.mark.parametrize(
    ("phase", "offered"),
    [
        (SUGGEST, ["Forward to APPROVE ▶"]),
        (APPROVE, ["◀ Back to SUGGEST", "Forward to VOTE ▶"]),
        (VOTE, ["◀ Back to APPROVE", "Forward to PICK ▶"]),
        (PICK, ["◀ Back to VOTE", "Forward to RUN ▶"]),
        (RUN, ["◀ Back to PICK"]),
    ],
)
def test_the_tab_offers_one_step_back_and_one_forward_or_one_at_either_end(admin, phase, offered):
    walk_to(phase)

    assert [heading(fragment) for fragment in moves(admin.get(TAB).text).values()] == offered


@pytest.mark.parametrize("phase", PHASES)
def test_unarmed_each_move_offers_only_its_arm_link(admin, phase):
    walk_to(phase)
    back, forward = neighbours(phase)

    shown = moves(admin.get(TAB).text)

    expected = {}
    if back:
        expected[back] = (f"{TAB}?from={phase}&arm={back}", f"◀ Move back to {back}…")
    if forward:
        expected[forward] = (f"{TAB}?from={phase}&arm={forward}", f"Move to {forward} ▶…")
    assert {to: arm_link(fragment) for to, fragment in shown.items()} == expected
    assert [confirm(fragment) for fragment in shown.values()] == [None] * len(expected)


@pytest.mark.parametrize(("from_phase", "to_phase"), EVERY_MOVE)
def test_each_moves_consequence_is_the_page_voters_see_after_it(admin, from_phase, to_phase):
    walk_to(from_phase)

    consequence = text(moves(admin.get(TAB).text)[to_phase])

    assert f"Everyone's page becomes “{PAGE_HEADINGS[to_phase]}”." in consequence


def consequences_of(admin, to_phase):
    return [text(sentence) for sentence in re.findall(r"<p>(.*?)</p>", moves(admin.get(TAB).text)[to_phase], re.S)]


def test_opening_the_ballot_lists_the_undecided_films_it_leaves_off_newest_first(admin, voters):
    for tmdb_id, title, approval in [(1, "The Thing", Approval.APPROVED), (2, "Cube", Approval.UNDECIDED), (3, "Pulse", Approval.DROPPED), (4, "<Possession>", Approval.UNDECIDED)]:
        Suggestion.objects.suggest(voters["ada"], a_tmdb_film(tmdb_id, title), "Pitch.")
        Suggestion.objects.filter(tmdb_id=tmdb_id).update(approval=approval)
    walk_to(APPROVE)

    page = moves(admin.get(TAB).text)[VOTE]

    assert "<p>Still undecided, so left off the ballot: <cite>&lt;Possession&gt;</cite>, <cite>Cube</cite>.</p>" in page


def test_opening_the_ballot_with_no_film_undecided_says_none_is(admin, voters):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1, "The Thing"), "Pitch.")
    Suggestion.objects.update(approval=Approval.DROPPED)
    walk_to(APPROVE)

    assert consequences_of(admin, VOTE)[1:] == ["No film is undecided."]


@pytest.mark.parametrize(("from_phase", "to_phase"), [move for move in EVERY_MOVE if move not in [(APPROVE, VOTE), (VOTE, APPROVE), (VOTE, PICK), (PICK, VOTE), (PICK, RUN), (RUN, PICK)]])
def test_no_other_move_prints_more_than_the_page_voters_see_after_it(admin, voters, from_phase, to_phase):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1, "Cube"), "Pitch.")
    walk_to(from_phase)

    assert consequences_of(admin, to_phase) == [f"Everyone's page becomes “{PAGE_HEADINGS[to_phase]}”."]


@pytest.mark.parametrize(
    ("from_phase", "to_phase", "added"),
    [
        (PICK, RUN, "Every film's trigger data is cleared, as DoesTheDogDie's terms ask, and fetched again if the evening is unpublished."),
        (RUN, PICK, "Trigger data is fetched again, oldest first."),
    ],
)
def test_the_moves_into_and_out_of_run_add_exactly_the_trigger_data_sentence(admin, voters, from_phase, to_phase, added):
    Suggestion.objects.suggest(voters["ada"], a_tmdb_film(1, "Cube"), "Pitch.")
    walk_to(from_phase)

    assert consequences_of(admin, to_phase) == [f"Everyone's page becomes “{PAGE_HEADINGS[to_phase]}”.", added]


@pytest.mark.parametrize(("from_phase", "to_phase"), EVERY_MOVE)
def test_arming_a_move_prints_the_act_and_cancel_and_moves_nothing(admin, from_phase, to_phase):
    walk_to(from_phase)
    before = history()

    shown = moves(armed(admin, from_phase, to_phase))

    assert history() == before
    assert confirm(shown[to_phase]) == (MOVE, {"from_phase": from_phase, "to_phase": to_phase}, ACTS[from_phase, to_phase], TAB)
    assert arm_link(shown[to_phase]) is None


def pending(fragment):
    """What the armed confirm reads once clicked, while the move and the refresh behind it run (#104)."""
    found = re.search(r'<button type="submit" data-pending="([^"]+)">', fragment)
    return found and html.unescape(found[1])


@pytest.mark.parametrize(("from_phase", "to_phase"), EVERY_MOVE)
def test_the_confirm_says_the_phase_is_moving_and_trigger_data_refreshing_or_clearing_once_clicked(admin, from_phase, to_phase):
    walk_to(from_phase)

    page = armed(admin, from_phase, to_phase)

    # Entering RUN fetches nothing, so it says what it does instead (#106).
    doing = "clearing" if to_phase == RUN else "refreshing"
    assert pending(moves(page)[to_phase]) == f"Moving to {to_phase} and {doing} trigger data…"
    # The script that disables it, so a second click posts nothing (#104).
    assert f'<script src="{static("console/pending.js")}" defer></script>' in page


@pytest.mark.parametrize(("from_phase", "to_phase"), EVERY_MOVE)
def test_armed_cancel_takes_the_arms_place_on_the_top_line_and_the_confirm_comes_after_the_consequences(admin, from_phase, to_phase):
    walk_to(from_phase)
    _, arm = arm_link(moves(admin.get(TAB).text)[to_phase])

    fragment = moves(armed(admin, from_phase, to_phase))[to_phase]

    assert cancel_link(fragment) == (TAB, arm)
    assert "<form" not in head(fragment)
    after_head = fragment.split("</div>", 1)[1]
    assert re.search(r"\A\s*(?:<p>[^<]*</p>\s*)+<form ", after_head)


def test_arming_one_move_leaves_the_other_unarmed(admin):
    walk_to(VOTE)

    shown = moves(armed(admin, VOTE, PICK))

    assert confirm(shown[APPROVE]) is None
    assert arm_link(shown[APPROVE]) == (f"{TAB}?from=VOTE&arm=APPROVE", "◀ Move back to APPROVE…")
    assert 'class="phase-move phase-move--forward phase-move--irreversible is-armed"' in armed(admin, VOTE, PICK)


@pytest.mark.parametrize(
    ("from_phase", "to_phase"),
    [(SUGGEST, APPROVE), (APPROVE, VOTE), (VOTE, RUN), (VOTE, "SETUP"), ("", PICK), (VOTE, "")],
)
def test_an_arm_from_a_stale_tab_or_for_no_neighbour_arms_nothing(admin, from_phase, to_phase):
    walk_to(VOTE)

    shown = moves(armed(admin, from_phase, to_phase))

    assert [confirm(fragment) for fragment in shown.values()] == [None, None]


@pytest.mark.parametrize(("from_phase", "to_phase"), EVERY_MOVE)
def test_confirming_moves_one_step_and_reloads_the_tab(admin, from_phase, to_phase):
    walk_to(from_phase)
    before = history()

    response = admin.post(MOVE, {"from_phase": from_phase, "to_phase": to_phase})

    assert (response.status_code, response.headers["Location"]) == (302, TAB)
    assert history() == [*before, to_phase]
    assert current() is to_phase


@pytest.mark.parametrize(
    ("from_phase", "to_phase", "elsewhere"),
    [
        (SUGGEST, APPROVE, [(SUGGEST, APPROVE)]),
        (APPROVE, VOTE, [(APPROVE, SUGGEST)]),
        (VOTE, PICK, [(VOTE, PICK), (PICK, RUN)]),
    ],
)
def test_a_stale_confirm_moves_nothing_and_the_tab_reloads_showing_the_current_phase(admin, from_phase, to_phase, elsewhere):
    walk_to(from_phase)
    action, fields, _, _ = confirm(moves(armed(admin, from_phase, to_phase))[to_phase])
    for before, after in elsewhere:
        move(before, after)
    moved_elsewhere = history()

    response = admin.post(action, fields, follow=True)

    assert history() == moved_elsewhere
    assert response.redirect_chain == [(TAB, 302)]
    assert re.search(r"<h1>(.*?)</h1>", response.text)[1] == f"The marathon is in {elsewhere[-1][1]}"


@pytest.mark.parametrize(
    "fields",
    [
        {"from_phase": VOTE, "to_phase": RUN},
        {"from_phase": VOTE, "to_phase": VOTE},
        {"from_phase": VOTE, "to_phase": "SETUP"},
        {"from_phase": VOTE},
        {"to_phase": PICK},
        {},
    ],
)
def test_a_confirm_that_is_not_one_step_from_the_current_phase_moves_nothing(admin, fields):
    walk_to(VOTE)
    before = history()

    response = admin.post(MOVE, fields)

    assert (response.status_code, response.headers["Location"]) == (302, TAB)
    assert history() == before


def test_the_move_route_answers_post_alone(admin):
    assert admin.get(MOVE).status_code == 405


def test_walking_suggest_to_run_and_back_through_the_tab_leaves_eight_moves(admin):
    for direction in ["forward"] * 4 + ["back"] * 4:
        phase = current()
        to_phase = getattr(neighbours(phase), direction)
        link, _ = arm_link(moves(admin.get(TAB).text)[to_phase])
        action, fields, _, _ = confirm(moves(admin.get(link).text)[to_phase])
        admin.post(action, fields)

    assert history() == [APPROVE, VOTE, PICK, RUN, PICK, VOTE, APPROVE, SUGGEST]
    assert current() is SUGGEST


@pytest.mark.parametrize("registered", [0, 1, 3])
def test_the_status_line_counts_the_voters_registered_and_links_the_roster_tab(admin, registered):
    for name in ["Ada", "Dani", "Hanna"][:registered]:
        Voter.objects.create_voter(name)

    page = admin.get(TAB).text

    status = status_line(page, "Voters")
    assert text(status) == f"Voters {registered} registered Roster tab"
    assert '<a href="/console/roster/">Roster tab</a>' in status


def status_line(page, label):
    lines = re.search(r'<ul class="console-status">(.*?)</ul>', page, re.S)[1]
    return next(line for line in re.findall(r"<li>(.*?)</li>", lines, re.S) if text(line).startswith(label))


@pytest.mark.parametrize("approvals, says", [([], "0 suggestions · 0 on the ballot"), (["approved"], "1 suggestion · 1 on the ballot"), (["approved", "undecided", "dropped", "approved"], "4 suggestions · 2 on the ballot")])
def test_the_films_line_counts_the_suggestions_and_the_ballot_and_links_the_films_tab(admin, approvals, says):
    voter = Voter.objects.create_voter("Ada")
    for tmdb_id, approval in enumerate(approvals, start=1):
        suggestion = Suggestion.objects.suggest(voter, a_tmdb_film(tmdb_id, f"Film {tmdb_id}"), "A pitch.")
        Suggestion.objects.filter(pk=suggestion.pk).update(approval=approval)

    status = status_line(admin.get(TAB).text, "Films")

    assert text(status) == f"Films {says} Films tab"
    assert '<a href="/console/films/">Films tab</a>' in status
