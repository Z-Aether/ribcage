"""Approving once VOTE has opened asks first and clears every done marker; dropping clears none; the console shows who is done (#15, #28, #124)."""

import html
from pathlib import Path
import re

import pytest
from django.conf import settings

from ribcage.ballot.board import candidates
from ribcage.ballot.done import set_done
from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.ballot.progress import of_every_voter
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval
from tests.http.test_approve_and_drop import APPROVED, DROPPED, UNDECIDED, approval_of, decide
from tests.http.test_ballot_page import film
from tests.http.test_films_tab import TAB, suggested, summary
from tests.http.test_phase import walk_to
from tests.http.test_roster_tab import CANCEL, text
from tests.http.test_roster_tab import TAB as ROSTER

PHASE_TAB = "/console/phase/"
DECIDE = "/console/films/approval/"


@pytest.fixture
def vote(voters):
    """VOTE has opened with one film on the ballot, two voters done and one undecided film to approve."""
    walk_to(Phase.VOTE)
    film(voters["Hanna"], "On the ballot")
    set_done(voters["ada"], True)
    set_done(voters["Dani"], True)
    return suggested(voters["Hanna"], "Undecided", UNDECIDED, runtime=90)


def done_ids():
    return set(DoneMarker.objects.values_list("voter_id", flat=True))


def arm(admin, suggestion):
    return admin.get(TAB, {"arm": suggestion.pk}).text


def confirm_of(page):
    form = re.search(r'<form method="post" action="([^"]+)" class="films-confirm" data-lands-on="([^"]+)">(.*?)</form>', page, re.S)
    if form is None:
        return None
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', form[3]))
    fields.pop("csrfmiddlewaretoken")
    says = [text(each) for each in re.findall(r"<p[^>]*>(.*?)</p>", form[3], re.S)]
    return fields, says


def test_approving_in_vote_clears_every_done_marker(admin, vote):
    decide(admin, vote, UNDECIDED, APPROVED)

    assert approval_of(vote) == APPROVED and done_ids() == set()


def test_re_approving_a_dropped_film_clears_every_done_marker(admin, voters, vote):
    dropped = film(voters["Hanna"], "Dropped", Approval.DROPPED)

    decide(admin, dropped, DROPPED, APPROVED)

    assert approval_of(dropped) == APPROVED and done_ids() == set()


def test_dropping_clears_no_marker_and_keeps_the_records(admin, voters, vote):
    shown = candidates().get()
    BallotRecord.objects.create(voter=voters["ada"], suggestion=shown, score=2)

    decide(admin, shown, APPROVED, DROPPED)

    assert approval_of(shown) == DROPPED
    assert done_ids() == {voters["ada"].pk, voters["Dani"].pk} and BallotRecord.objects.count() == 1


def test_a_refused_approval_clears_nothing(admin, vote):
    decide(admin, vote, APPROVED, APPROVED)

    assert len(done_ids()) == 2


def test_approving_before_vote_has_ever_opened_is_instant_and_clears_nothing(admin, voters):
    walk_to(Phase.APPROVE)
    set_done(voters["ada"], True)
    undecided = suggested(voters["Hanna"], "Cube", runtime=90)

    page = arm(admin, undecided)
    decide(admin, undecided, UNDECIDED, APPROVED)

    assert confirm_of(page) is None
    assert 'name="to_approval" value="approved">Approve</button>' in page
    assert approval_of(undecided) == APPROVED and len(done_ids()) == 1


def test_after_a_move_back_to_approve_it_still_asks_and_clears(admin, vote):
    move(Phase.VOTE, Phase.APPROVE)

    page = arm(admin, vote)
    decide(admin, vote, UNDECIDED, APPROVED)

    assert confirm_of(page) is not None and done_ids() == set()


def test_approve_is_an_arming_link_once_vote_has_opened_and_drop_stays_a_button(admin, vote):
    page = admin.get(TAB).text

    row = re.search(rf'<tr data-suggestion="{vote.pk}".*?</tr>', page, re.S)[0]
    assert f'<a class="button button--quiet" href="{TAB}?arm={vote.pk}">Approve</a>' in row
    assert 'name="to_approval" value="approved"' not in row and 'name="to_approval" value="dropped"' in row


def test_the_arm_keeps_the_filter(admin, vote):
    page = admin.get(TAB, {"show": "undecided"}).text

    assert f'href="{TAB}?show=undecided&amp;arm={vote.pk}"' in page


def test_arming_moves_nothing(admin, vote):
    before = (approval_of(vote), done_ids())

    arm(admin, vote)

    assert (approval_of(vote), done_ids()) == before


def test_the_confirm_prints_the_done_count_before_and_after_then_the_button_on_a_line_of_its_own(admin, vote):
    page = arm(admin, vote)

    fields, says = confirm_of(page)
    assert says[0] == "Adds it to every voter's ballot and clears every done marker: 2 of 3 → 0 of 3."
    assert says[-1] == "Approve Undecided" and len(says) == 2
    assert fields == {"suggestion": str(vote.pk), "from_approval": "undecided", "show": "all", "to_approval": "approved"}
    assert '<p class="console-confirm"><button type="submit">' in page


@pytest.mark.parametrize("phase", [Phase.PICK, Phase.RUN])
def test_the_confirm_in_pick_or_run_says_vote_is_closed_and_must_be_reopened(admin, vote, phase):
    move(Phase.VOTE, Phase.PICK)
    if phase is Phase.RUN:
        move(Phase.PICK, Phase.RUN)

    _, says = confirm_of(arm(admin, vote))

    assert says[1] == "VOTE is closed, so nobody can score the film unless VOTE is reopened." and len(says) == 3


def test_cancel_takes_approves_place_and_the_confirm_sits_under_the_row(admin, vote):
    page = arm(admin, vote)

    row = re.search(rf'<tr data-suggestion="{vote.pk}".*?</tr>', page, re.S)[0]
    assert re.search(CANCEL, row).groups() == (TAB, "Approve")
    assert f'data-keeps-place="{vote.pk}"' in row
    assert re.search(rf'<tr class="ledger__detail" data-place-of="{vote.pk}">\s*<td colspan="\d">\s*<form', page)


def test_an_arm_for_a_film_that_cannot_be_approved_arms_nothing(admin, voters, vote):
    on_the_ballot = candidates().get()
    no_runtime = suggested(voters["Hanna"], "No runtime", runtime=None)

    assert confirm_of(admin.get(TAB, {"arm": on_the_ballot.pk}).text) is None
    assert confirm_of(admin.get(TAB, {"arm": no_runtime.pk}).text) is None
    assert confirm_of(admin.get(TAB, {"arm": "nonsense"}).text) is None


def test_a_voter_marking_done_between_the_arm_and_the_confirm_is_cleared_all_the_same(admin, voters, vote):
    fields, _ = confirm_of(arm(admin, vote))
    set_done(voters["Hanna"], True)

    admin.post(DECIDE, fields)

    assert approval_of(vote) == APPROVED and done_ids() == set()


def test_a_stale_confirm_changes_nothing(admin, voters, vote):
    fields, _ = confirm_of(arm(admin, vote))
    decide(admin, vote, UNDECIDED, DROPPED)
    set_done(voters["Hanna"], True)

    admin.post(DECIDE, fields)

    assert approval_of(vote) == DROPPED and voters["Hanna"].pk in done_ids()


def test_the_films_tab_counts_who_is_done_once_vote_has_opened(admin, vote):
    assert summary(admin.get(TAB).text).endswith("· 2 of 3 done")


def test_the_films_tab_has_no_done_count_before_vote_has_opened(admin, voters):
    walk_to(Phase.APPROVE)

    assert "done" not in summary(admin.get(TAB).text)


def status_lines(page):
    return text(re.search(r'<ul class="console-status">(.*?)</ul>', page, re.S)[1])


def test_the_phase_tab_counts_who_is_done_once_vote_has_opened(admin, vote):
    assert "Voters 3 registered · 2 done Roster tab" in status_lines(admin.get(PHASE_TAB).text)


def test_the_phase_tab_has_no_done_count_before_vote_has_opened(admin, voters):
    walk_to(Phase.APPROVE)

    assert "done" not in status_lines(admin.get(PHASE_TAB).text)


def roster_cells(page):
    rows = re.findall(r'<tr data-voter="\d+"[^>]*>\s*<td class="roster__name">(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', page, re.S)
    return [(html.unescape(name), text(scored), text(vetoes), text(done)) for name, scored, vetoes, done in rows]


def test_the_roster_reads_a_dash_in_each_column_before_vote_has_opened(admin, voters):
    walk_to(Phase.APPROVE)

    assert roster_cells(admin.get(ROSTER).text) == [(name, "—", "—", "—") for name in ["ada", "Dani", "Hanna"]]


def test_the_roster_shows_scored_vetoes_and_done_once_vote_has_opened(admin, voters, vote):
    second = film(voters["Hanna"], "Second")
    third = film(voters["Hanna"], "Third")
    ada, dani = voters["ada"], voters["Dani"]
    BallotRecord.objects.create(voter=ada, suggestion=second, score=3)
    BallotRecord.objects.create(voter=ada, suggestion=third, vetoed=True)
    BallotRecord.objects.create(voter=dani, suggestion=second, seen_it=True)
    dropped = film(voters["Hanna"], "Dropped", Approval.DROPPED)
    BallotRecord.objects.create(voter=ada, suggestion=dropped, score=1)
    dropped_vetoed = film(voters["Hanna"], "Dropped and vetoed", Approval.DROPPED)
    BallotRecord.objects.create(voter=ada, suggestion=dropped_vetoed, vetoed=True)
    BallotRecord.objects.create(voter=dani, suggestion=dropped_vetoed, vetoed=True)

    assert roster_cells(admin.get(ROSTER).text) == [("ada", "2 / 3", "1", "done"), ("Dani", "0 / 3", "0", "done"), ("Hanna", "0 / 3", "0", "not yet")]


def test_the_roster_sits_in_a_sideways_scrolling_frame_and_the_confirm_keeps_to_its_width(admin, voters, vote):
    page = admin.get(ROSTER).text
    css = (Path(settings.BASE_DIR) / "ribcage/static/theme/theme.css").read_text(encoding="utf-8")

    assert re.search(r'<div class="roster__frame" data-keeps-scroll>\s*<table class="ledger roster">', page)
    assert re.search(r"\.films-ledger__frame,\s*\.roster__frame \{", css)
    sticky = re.search(r"\.ledger \.ledger__detail :is\(\.films-confirm[^{]*\{([^}]*)\}", css)
    assert sticky and "position: sticky" in sticky[1] and "max-width: calc(100cqi" in sticky[1]


def test_progress_is_every_voters_in_one_query_and_counts_as_the_ballot_does(voters, vote, django_assert_num_queries):
    second = film(voters["Hanna"], "Second")
    BallotRecord.objects.create(voter=voters["ada"], suggestion=second, score=0)

    with django_assert_num_queries(1):
        found = of_every_voter()

    assert [(each.name, each.scored, each.vetoes, each.done) for each in found] == [("ada", 1, 0, True), ("Dani", 0, 0, True), ("Hanna", 0, 0, False)]
