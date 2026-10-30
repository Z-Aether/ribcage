"""Veto and seen it before VOTE: set and cleared from the opened card in SUGGEST and APPROVE, on any film in the pool, saved at once, with the row alone answered (#10, #34, #152)."""

import re

import pytest

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import VoteBar
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note, Suggestion
from tests.http.test_ballot_page import HTMX, film, place, region, signed_in, tiles_on, walk_on_to
from tests.http.test_phase import walk_to
from tests.http.test_runtime_pencil import pencils_on
from tests.http.test_withdraw import arms_on

VETO, SEEN = "/ballot/veto/", "/ballot/seen/"
BEFORE_VOTE = [Phase.SUGGEST, Phase.APPROVE]
DECISIONS = [Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED]


def veto(client, suggestion, state, **extra):
    return client.post(VETO, {"suggestion": str(suggestion.pk), "veto": state, "card": "1"}, **extra)


def seen(client, suggestion, state, **extra):
    return client.post(SEEN, {"suggestion": str(suggestion.pk), "seen": state, "card": "1"}, **extra)


def record(voter, suggestion):
    return BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()


@pytest.fixture
def pool(voters):
    hanna = voters["Hanna"]
    return {"voters": voters, "ada": voters["ada"], "client": signed_in(voters["ada"]), "hanna": hanna, "one": film(hanna, "One", Approval.UNDECIDED)}


@pytest.mark.parametrize("phase", BEFORE_VOTE)
@pytest.mark.parametrize("decision", DECISIONS)
def test_a_veto_and_seen_it_are_set_and_cleared_on_any_film_in_the_pool(pool, phase, decision):
    walk_to(phase)
    each = film(pool["hanna"], "Decided", decision)

    veto(pool["client"], each, "1", headers=HTMX)
    seen(pool["client"], each, "1", headers=HTMX)
    assert (record(pool["ada"], each).vetoed, record(pool["ada"], each).seen_it) == (True, True)

    veto(pool["client"], each, "0", headers=HTMX)
    assert (record(pool["ada"], each).vetoed, record(pool["ada"], each).seen_it) == (False, True)
    seen(pool["client"], each, "0", headers=HTMX)
    assert record(pool["ada"], each) is None


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_a_repeat_changes_nothing_and_a_plain_post_redirects(pool, phase):
    walk_to(phase)

    veto(pool["client"], pool["one"], "1", headers=HTMX)
    veto(pool["client"], pool["one"], "1", headers=HTMX)
    assert BallotRecord.objects.count() == 1
    veto(pool["client"], pool["one"], "0", headers=HTMX)
    veto(pool["client"], pool["one"], "0", headers=HTMX)
    assert BallotRecord.objects.count() == 0
    plain = veto(pool["client"], pool["one"], "1")

    assert BallotRecord.objects.count() == 1 and (plain.status_code, plain.headers["Location"]) == (302, "/")


@pytest.mark.parametrize("phase", [Phase.PICK, Phase.RUN])
def test_both_are_refused_after_vote_by_the_phase_check(pool, phase):
    walk_to(Phase.VOTE)
    walk_on_to(phase)

    answers = [veto(pool["client"], pool["one"], "1", headers=HTMX), seen(pool["client"], pool["one"], "1", headers=HTMX)]

    assert all(answer.headers["HX-Redirect"] == "/" for answer in answers) and BallotRecord.objects.count() == 0


def test_both_are_refused_in_pick_with_the_ballot_walked_to_it(pool):
    walk_to(Phase.PICK)

    answers = [veto(pool["client"], pool["one"], "1", headers=HTMX), seen(pool["client"], pool["one"], "1", headers=HTMX)]

    assert all(answer.headers["HX-Redirect"] == "/" for answer in answers) and BallotRecord.objects.count() == 0


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_a_score_post_outside_vote_is_still_refused_and_so_is_a_veto_posted_to_the_placement(pool, phase):
    walk_to(phase)

    answers = [place(pool["client"], pool["one"], 2, headers=HTMX), place(pool["client"], pool["one"], "veto", headers=HTMX)]

    assert all(answer.headers["HX-Redirect"] == "/" for answer in answers) and BallotRecord.objects.count() == 0


def test_the_early_veto_route_is_no_way_to_veto_in_vote_where_the_placement_is(pool):
    walk_to(Phase.VOTE)
    candidate = film(pool["hanna"], "Candidate")

    answer = veto(pool["client"], candidate, "1", headers=HTMX)

    assert answer.headers["HX-Redirect"] == "/" and BallotRecord.objects.count() == 0


def test_seen_it_in_vote_still_acts_on_candidates_alone(pool):
    walk_to(Phase.VOTE)
    candidate = film(pool["hanna"], "Candidate")

    assert "HX-Redirect" not in seen(pool["client"], candidate, "1", headers=HTMX).headers
    answer = seen(pool["client"], pool["one"], "1", headers=HTMX)

    assert answer.headers["HX-Redirect"] == "/" and BallotRecord.objects.filter(suggestion=pool["one"]).count() == 0


@pytest.mark.parametrize("posted", [{"veto": "maybe"}, {"veto": ""}, {"suggestion": "x", "veto": "1"}, {"suggestion": "999", "veto": "1"}])
def test_a_stale_or_unnamed_post_reloads_and_writes_nothing(pool, posted):
    named = {"suggestion": str(pool["one"].pk), **posted}

    answer = pool["client"].post(VETO, named, headers=HTMX)

    assert "HX-Redirect" in answer.headers and BallotRecord.objects.count() == 0


def test_a_veto_replaces_the_voters_score_after_a_move_back_to_suggest_and_taking_it_back_leaves_none(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 3)
    walk_on_to(Phase.SUGGEST)

    veto(pool["client"], approved, "1", headers=HTMX)
    assert (record(pool["ada"], approved).score, record(pool["ada"], approved).vetoed) == (None, True)
    veto(pool["client"], approved, "0", headers=HTMX)

    assert record(pool["ada"], approved) is None


def test_taking_back_a_veto_the_film_never_had_leaves_its_score_alone(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 3)
    walk_on_to(Phase.APPROVE)

    veto(pool["client"], approved, "0", headers=HTMX)

    assert record(pool["ada"], approved).score == 3


def test_seen_it_leaves_a_score_alone(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 2)
    walk_on_to(Phase.APPROVE)

    seen(pool["client"], approved, "1", headers=HTMX)

    assert (record(pool["ada"], approved).score, record(pool["ada"], approved).seen_it) == (2, True)


def test_the_marks_are_the_voters_own(pool):
    veto(pool["client"], pool["one"], "1", headers=HTMX)

    veto(signed_in(pool["voters"]["Dani"]), pool["one"], "0", headers=HTMX)

    assert record(pool["ada"], pool["one"]).vetoed and record(pool["voters"]["Dani"], pool["one"]) is None


def test_a_film_vetoed_in_suggest_and_approved_sits_in_the_veto_band_and_counts_as_scored(pool):
    veto(pool["client"], pool["one"], "1", headers=HTMX)
    walk_to(Phase.VOTE)
    Suggestion.objects.filter(pk=pool["one"].pk).update(approval=Approval.APPROVED)
    other = film(pool["hanna"], "Other")

    page = pool["client"].get("/").text

    assert region(page, "veto") == [pool["one"].pk] and region(page, "unsorted") == [other.pk]
    assert "1 of 2 scored" in page and "1 left" in page


def test_a_film_only_seen_sits_in_unsorted_greyed(pool):
    seen(pool["client"], pool["one"], "1", headers=HTMX)
    walk_to(Phase.VOTE)
    Suggestion.objects.filter(pk=pool["one"].pk).update(approval=Approval.APPROVED)

    page = pool["client"].get("/").text

    assert region(page, "unsorted") == [pool["one"].pk] and "0 of 1 scored" in page
    assert re.search(rf'<li class="tile is-seen-it" data-suggestion="{pool["one"].pk}"', page)
    assert tiles_on(page) == [pool["one"].pk]


def test_another_voters_early_marks_leave_the_suggesters_withdraw_and_pencil(pool):
    own = film(pool["ada"], "Ada's own", Approval.UNDECIDED)
    veto(signed_in(pool["voters"]["Dani"]), own, "1", headers=HTMX)
    seen(signed_in(pool["voters"]["Hanna"]), own, "1", headers=HTMX)

    page = pool["client"].get("/").text

    assert own.pk in arms_on(page) and own.pk in pencils_on(page)


def test_the_suggesters_own_marks_change_neither_withdraw_nor_the_pencil(pool):
    own = film(pool["ada"], "Ada's own", Approval.UNDECIDED)
    veto(pool["client"], own, "1", headers=HTMX)
    seen(pool["client"], own, "1", headers=HTMX)

    page = pool["client"].get("/").text

    assert own.pk in arms_on(page) and own.pk in pencils_on(page)


@pytest.mark.parametrize("marked", [False, True])
@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_opened_cards_row_has_the_veto_and_seen_it_and_no_score_pills(pool, phase, marked):
    walk_to(phase)
    if marked:
        veto(pool["client"], pool["one"], "1", headers=HTMX)
        seen(pool["client"], pool["one"], "1", headers=HTMX)

    row = re.search(r'<div class="vote-bar__scores[^"]*">.*?</form>\s*</div>', pool["client"].get("/").text, re.S)[0]

    assert "vote-bar__scores--marks" in row and "Your veto" in row
    assert row.count('class="vote-bar__score ') == 1 and "score--veto" in row and "Seen it" in row
    assert 'hx-post="/ballot/veto/"' in row and "/ballot/place/" not in row
    assert 'hx-post="/ballot/seen/"' in row
    # The answers replace the row itself, not the pill or the form that posted (#152).
    pill = re.search(r"<button[^>]*vote-bar__veto[^>]*>", row)[0]
    form = re.search(r"<form[^>]*vote-seen[^>]*>", row)[0]
    for control in (pill, form):
        assert 'hx-target="closest .vote-bar__scores"' in control and 'hx-swap="outerHTML"' in control


def test_the_score_pills_follow_the_scale_alone():
    assert VoteBar(scale=SCALE).scoring and not VoteBar(scale=()).scoring


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_row_reads_what_the_voter_marked_when_the_page_is_drawn_and_no_one_elses(pool, phase):
    walk_to(phase)
    veto(pool["client"], pool["one"], "1", headers=HTMX)
    seen(pool["client"], pool["one"], "1", headers=HTMX)

    page = pool["client"].get("/").text
    other = signed_in(pool["voters"]["Dani"]).get("/").text

    assert "<b>−2</b> Vetoed" in page and '"veto": "0"' in page and "checked" in page
    assert "Vetoed" not in other and "checked" not in other


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_answer_is_the_row_alone_and_the_note_box_and_runtime_box_are_never_drawn(pool, phase):
    walk_to(phase)

    answer = veto(pool["client"], pool["one"], "1", headers=HTMX).text
    seen_answer = seen(pool["client"], pool["one"], "1", headers=HTMX).text

    assert answer.lstrip().startswith('<div class="vote-bar__scores') and "<b>−2</b> Vetoed" in answer
    for each in (answer, seen_answer):
        assert "<textarea" not in each and 'name="runtime"' not in each and "<article" not in each and "data-withdraw" not in each
    # Seen it answers the row holding the veto already made.
    assert "<b>−2</b> Vetoed" in seen_answer and "checked" in seen_answer


def test_the_veto_answer_fills_and_empties_the_note_boxs_veto_reason_line_out_of_band(pool):
    on = veto(pool["client"], pool["one"], "1", headers=HTMX).text
    off = veto(pool["client"], pool["one"], "0", headers=HTMX).text

    hint = f'id="note-hint-{pool["one"].pk}" hx-swap-oob="true"'
    assert hint in on and "shows as your veto reason" in on and 'class="note-box__hint"' in on
    assert hint in off and "veto reason" not in off and 'class="note-box__hint"' not in off


def test_the_veto_reason_line_is_on_the_page_only_while_the_voter_vetoes(pool):
    walk_to(Phase.APPROVE)
    assert "veto reason" not in pool["client"].get("/").text
    veto(pool["client"], pool["one"], "1", headers=HTMX)

    page = pool["client"].get("/").text

    assert "Your note on this film shows as your veto reason" in page and f'aria-describedby="note-hint-{pool["one"].pk}"' in page


def test_the_veto_leaves_the_voters_note_untouched(pool):
    Note.objects.create(suggestion=pool["one"], author=pool["ada"], text="Not for me.")

    veto(pool["client"], pool["one"], "1", headers=HTMX)
    veto(pool["client"], pool["one"], "0", headers=HTMX)

    assert Note.objects.get(author=pool["ada"]).text == "Not for me."


def test_a_note_saved_from_the_card_still_draws_the_row_with_the_marks(pool):
    veto(pool["client"], pool["one"], "1", headers=HTMX)

    saved = pool["client"].post("/note/", {"suggestion": str(pool["one"].pk), "text": "Nope."}, headers=HTMX).text

    assert "<b>−2</b> Vetoed" in saved
