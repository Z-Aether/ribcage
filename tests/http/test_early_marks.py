"""Veto and seen it before VOTE: toggled on the opened card in SUGGEST and APPROVE, on any film in the pool, and written by the card's one Save with the note and the runtime (#10, #34, #152)."""

import re

import pytest
from django.conf import settings

from ribcage.ballot.board import SCALE
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import VoteBar
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note, Suggestion
from tests.http.test_ballot_page import HTMX, film, place, region, signed_in, tiles_on, walk_on_to
from tests.http.test_phase import walk_to
from tests.http.test_runtime_pencil import pencils_on
from tests.http.test_withdraw import arms_on

NOTE = "/note/"
BEFORE_VOTE = [Phase.SUGGEST, Phase.APPROVE]
DECISIONS = [Approval.UNDECIDED, Approval.APPROVED, Approval.DROPPED]


def record(voter, suggestion):
    return BallotRecord.objects.filter(voter=voter, suggestion=suggestion).first()


def marks(voter, suggestion):
    """The voter's saved (veto, seen it) on the film."""
    own = record(voter, suggestion)
    return (own.vetoed, own.seen_it) if own else (False, False)


def card_post(voter, suggestion, text="", veto=None, seen=None, runtime=None):
    """What the card's form posts: the toggles' states and the states the card was drawn with, as the browser sends them (#152)."""
    drawn_veto, drawn_seen = marks(voter, suggestion)
    posted = {"suggestion": str(suggestion.pk), "text": text}
    if veto is not None:
        posted.update(veto="1" if veto else "0", veto_was="1" if drawn_veto else "0")
    if seen is not None:
        posted.update(seen="1" if seen else "0", seen_was="1" if drawn_seen else "0")
    if runtime is not None:
        posted["runtime"] = runtime
    return posted


def save(client, voter, suggestion, text="", veto=None, seen=None, runtime=None, **extra):
    return client.post(NOTE, card_post(voter, suggestion, text, veto, seen, runtime), **extra)


@pytest.fixture
def pool(voters):
    hanna = voters["Hanna"]
    return {"voters": voters, "ada": voters["ada"], "client": signed_in(voters["ada"]), "hanna": hanna, "one": film(hanna, "One", Approval.UNDECIDED)}


def saved(pool, **toggles):
    return save(pool["client"], pool["ada"], pool["one"], headers=HTMX, **toggles)


@pytest.mark.parametrize("phase", BEFORE_VOTE)
@pytest.mark.parametrize("decision", DECISIONS)
def test_save_sets_and_clears_a_veto_and_seen_it_on_any_film_in_the_pool(pool, phase, decision):
    walk_to(phase)
    each = film(pool["hanna"], "Decided", decision)
    client, ada = pool["client"], pool["ada"]

    save(client, ada, each, veto=True, seen=True, headers=HTMX)
    assert marks(ada, each) == (True, True)

    save(client, ada, each, veto=False, headers=HTMX)
    assert marks(ada, each) == (False, True)
    save(client, ada, each, seen=False, headers=HTMX)
    assert record(ada, each) is None


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_save_takes_the_note_the_open_runtime_box_and_both_toggles_together(pool, phase):
    walk_to(phase)

    answer = saved(pool, text="Not for me.", veto=True, seen=True, runtime="95" if phase is Phase.SUGGEST else None)

    assert marks(pool["ada"], pool["one"]) == (True, True)
    assert Note.objects.get(author=pool["ada"]).text == "Not for me."
    pool["one"].refresh_from_db()
    assert pool["one"].runtime == (95 if phase is Phase.SUGGEST else 100)
    # The card closes, listing the new marks (#132, #153).
    assert 'class="film-card"' in answer.text and "is-open" not in answer.text
    assert "vetoed by ada" in answer.text and "Not for me." in answer.text


def test_a_refused_note_writes_no_mark_and_no_runtime(pool):
    answer = saved(pool, text="x" * (settings.NOTE_MAX_LENGTH + 1), veto=True, seen=True, runtime="95")

    assert BallotRecord.objects.count() == 0 and Note.objects.count() == 0
    pool["one"].refresh_from_db()
    assert pool["one"].runtime == 100
    # The card stays open with the toggles as the voter set them, against what is saved.
    assert "is-open" in answer.text
    assert re.search(r'<input type="checkbox"[^>]*name="veto"[^>]*data-saved="0"[^>]* checked', answer.text)
    assert re.search(r'<input type="checkbox"[^>]*name="seen"[^>]*data-saved="0"[^>]* checked', answer.text)


def test_a_refused_runtime_writes_no_mark_and_no_note(pool):
    answer = saved(pool, text="A note.", veto=True, seen=True, runtime="nine")

    assert BallotRecord.objects.count() == 0 and Note.objects.count() == 0
    assert "is-open" in answer.text and "runtime__refusal" in answer.text


def test_a_refused_save_that_clears_a_mark_keeps_the_box_unticked_against_what_is_saved(pool):
    saved(pool, veto=True)

    answer = saved(pool, text="x" * (settings.NOTE_MAX_LENGTH + 1), veto=False)

    assert marks(pool["ada"], pool["one"]) == (True, False)
    assert re.search(r'<input type="checkbox"[^>]*name="veto"[^>]*data-saved="1"(?![^>]*checked)', answer.text)


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_a_plain_post_saves_the_toggles_and_redirects(pool, phase):
    walk_to(phase)

    plain = save(pool["client"], pool["ada"], pool["one"], text="No.", veto=True, seen=True)

    assert marks(pool["ada"], pool["one"]) == (True, True) and (plain.status_code, plain.headers["Location"]) == (302, "/")


def test_a_save_with_the_toggles_as_drawn_changes_no_mark(pool):
    saved(pool, veto=True)
    # A page drawn before the veto was made elsewhere posts the old state and writes nothing of it.
    stale = card_post(pool["ada"], pool["one"], "Hm.", veto=False)
    stale["veto_was"] = "0"
    stale["veto"] = "0"

    pool["client"].post(NOTE, stale, headers=HTMX)

    assert marks(pool["ada"], pool["one"]) == (True, False)


def test_a_save_that_posts_no_toggle_leaves_the_marks_alone(pool):
    saved(pool, veto=True, seen=True)

    save(pool["client"], pool["ada"], pool["one"], text="Only words.", headers=HTMX)

    assert marks(pool["ada"], pool["one"]) == (True, True)


@pytest.mark.parametrize("posted", [{"veto": "maybe"}, {"veto": ""}, {"seen": "yes"}])
def test_a_toggle_naming_no_state_is_no_write(pool, posted):
    pool["client"].post(NOTE, {"suggestion": str(pool["one"].pk), "text": "", **posted}, headers=HTMX)

    assert BallotRecord.objects.count() == 0


@pytest.mark.parametrize("phase", [Phase.PICK, Phase.RUN])
def test_save_is_refused_after_vote_by_the_phase_check(pool, phase):
    walk_to(Phase.VOTE)
    walk_on_to(phase)

    answer = save(pool["client"], pool["ada"], pool["one"], veto=True, seen=True, headers=HTMX)

    assert answer.headers["HX-Redirect"] == "/" and BallotRecord.objects.count() == 0


def test_the_early_veto_route_is_gone(pool):
    walk_to(Phase.SUGGEST)

    assert pool["client"].post("/ballot/veto/", {"suggestion": str(pool["one"].pk), "veto": "1"}, headers=HTMX).status_code == 404


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_seen_it_route_is_vote_alone_even_for_an_approved_film(pool, phase):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    walk_on_to(phase)

    refused = pool["client"].post("/ballot/seen/", {"suggestion": str(approved.pk), "seen": "1"}, headers=HTMX)

    assert refused.headers["HX-Redirect"] == "/" and BallotRecord.objects.count() == 0


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_a_score_post_outside_vote_is_still_refused(pool, phase):
    walk_to(phase)

    answers = [place(pool["client"], pool["one"], 2, headers=HTMX), place(pool["client"], pool["one"], "veto", headers=HTMX)]

    assert all(answer.headers["HX-Redirect"] == "/" for answer in answers) and BallotRecord.objects.count() == 0


def test_a_veto_saved_after_a_move_back_to_suggest_replaces_the_voters_score_and_taking_it_back_leaves_none(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 3)
    walk_on_to(Phase.SUGGEST)

    save(pool["client"], pool["ada"], approved, veto=True, headers=HTMX)
    assert (record(pool["ada"], approved).score, record(pool["ada"], approved).vetoed) == (None, True)
    save(pool["client"], pool["ada"], approved, veto=False, headers=HTMX)

    assert record(pool["ada"], approved) is None


def test_taking_back_a_veto_the_film_never_had_leaves_its_score_alone(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 3)
    walk_on_to(Phase.APPROVE)
    stale = card_post(pool["ada"], approved, veto=False)
    stale["veto_was"] = "1"

    pool["client"].post(NOTE, stale, headers=HTMX)

    assert record(pool["ada"], approved).score == 3


def test_seen_it_saved_leaves_a_score_alone(pool):
    walk_to(Phase.VOTE)
    approved = film(pool["hanna"], "Approved")
    place(pool["client"], approved, 2)
    walk_on_to(Phase.APPROVE)

    save(pool["client"], pool["ada"], approved, seen=True, headers=HTMX)

    assert (record(pool["ada"], approved).score, record(pool["ada"], approved).seen_it) == (2, True)


def test_the_marks_are_the_voters_own(pool):
    saved(pool, veto=True)
    dani = pool["voters"]["Dani"]

    save(signed_in(dani), dani, pool["one"], veto=False, seen=False, headers=HTMX)

    assert record(pool["ada"], pool["one"]).vetoed and record(dani, pool["one"]) is None


def test_a_veto_leaves_the_voters_note_untouched_when_saved_with_it(pool):
    Note.objects.create(suggestion=pool["one"], author=pool["ada"], text="Not for me.")

    saved(pool, text="Not for me.", veto=True)
    saved(pool, text="Not for me.", veto=False)

    assert Note.objects.get(author=pool["ada"]).text == "Not for me."


def test_a_film_withdrawn_since_reloads_the_tab_and_writes_nothing(pool):
    posted = card_post(pool["ada"], pool["one"], veto=True)
    pool["one"].delete()

    answer = pool["client"].post(NOTE, posted, headers=HTMX)

    assert "HX-Redirect" in answer.headers and BallotRecord.objects.count() == 0


def test_a_film_vetoed_in_suggest_and_approved_sits_in_the_veto_band_and_counts_as_scored(pool):
    saved(pool, veto=True)
    walk_to(Phase.VOTE)
    Suggestion.objects.filter(pk=pool["one"].pk).update(approval=Approval.APPROVED)
    other = film(pool["hanna"], "Other")

    page = pool["client"].get("/").text

    assert region(page, "veto") == [pool["one"].pk] and region(page, "unsorted") == [other.pk]
    assert "1 of 2 scored" in page and "1 left" in page


def test_a_film_only_seen_sits_in_unsorted_greyed(pool):
    saved(pool, seen=True)
    walk_to(Phase.VOTE)
    Suggestion.objects.filter(pk=pool["one"].pk).update(approval=Approval.APPROVED)

    page = pool["client"].get("/").text

    assert region(page, "unsorted") == [pool["one"].pk] and "0 of 1 scored" in page
    assert re.search(rf'<li class="tile is-seen-it" data-suggestion="{pool["one"].pk}"', page)
    assert tiles_on(page) == [pool["one"].pk]


def test_another_voters_early_marks_leave_the_suggesters_withdraw_and_pencil(pool):
    own = film(pool["ada"], "Ada's own", Approval.UNDECIDED)
    dani, hanna = pool["voters"]["Dani"], pool["voters"]["Hanna"]
    save(signed_in(dani), dani, own, veto=True, headers=HTMX)
    save(signed_in(hanna), hanna, own, seen=True, headers=HTMX)

    page = pool["client"].get("/").text

    assert own.pk in arms_on(page) and own.pk in pencils_on(page)


def test_the_suggesters_own_marks_change_neither_withdraw_nor_the_pencil(pool):
    own = film(pool["ada"], "Ada's own", Approval.UNDECIDED)
    save(pool["client"], pool["ada"], own, text="Mine.", veto=True, seen=True, headers=HTMX)

    page = pool["client"].get("/").text

    assert marks(pool["ada"], own) == (True, True)
    assert own.pk in arms_on(page) and own.pk in pencils_on(page)


def row_of(page):
    return re.search(r'<div class="vote-bar__scores[^"]*">.*?</label>\s*</div>\s*</div>', page, re.S)[0]


@pytest.mark.parametrize("marked", [False, True])
@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_opened_cards_row_is_two_toggles_joined_to_the_note_form_with_no_score_pills_and_no_post(pool, phase, marked):
    walk_to(phase)
    if marked:
        saved(pool, veto=True, seen=True)
    page = pool["client"].get("/").text
    row = row_of(page)
    form_id = f'note-{pool["one"].pk}'

    assert "vote-bar__scores--marks" in row and "Your veto" in row and "Seen it" in row
    assert row.count('class="vote-bar__score ') == 1 and "<button" not in row and "<form" not in row and "hx-post" not in row
    for name in ("veto", "seen"):
        box = re.search(rf'<input type="checkbox"[^>]*name="{name}"[^>]*>', row)[0]
        assert f'form="{form_id}"' in box and f'data-saved="{int(marked)}"' in box and ('checked' in box) is marked
        # The unchecked state and the state drawn with post beside the box (#152).
        assert row.count(f'<input type="hidden" name="{name}" value="0" form="{form_id}">') == 1
        assert row.count(f'<input type="hidden" name="{name}_was" value="{int(marked)}" form="{form_id}">') == 1
    assert f'id="{form_id}"' in page and "/ballot/" not in row


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_row_reads_what_the_voter_saved_when_the_page_is_drawn_and_no_one_elses(pool, phase):
    walk_to(phase)
    saved(pool, veto=True, seen=True)

    other = signed_in(pool["voters"]["Dani"]).get("/").text

    assert not re.search(r'<input type="checkbox"[^>]*name="(veto|seen)"[^>]* checked', other)
    assert re.search(r'<input type="checkbox"[^>]*name="veto"[^>]* checked', pool["client"].get("/").text)


@pytest.mark.parametrize("phase", BEFORE_VOTE)
def test_the_veto_reason_line_is_always_drawn_and_left_to_the_veto_box(pool, phase):
    walk_to(phase)

    page = pool["client"].get("/").text

    # Shown or hidden by the page's style from the box's state, so a pending veto shows it before it is saved (#152).
    assert re.search(r'<p class="note-box__hint note-box__hint--follows" id="note-hint-\d+">Your note on this film shows as your veto reason', page)
    assert "aria-describedby" not in page


def test_the_pitch_reads_as_the_veto_reason_on_the_suggesters_own_card(pool):
    own = film(pool["ada"], "Ada's own", Approval.UNDECIDED)

    page = pool["client"].get("/").text

    assert f'id="note-hint-{own.pk}">Your pitch shows as your veto reason' in page


def test_the_score_pills_follow_the_scale_alone():
    assert VoteBar(scale=SCALE).scoring and not VoteBar(scale=()).scoring


def test_a_pending_toggle_shows_against_what_is_saved():
    bar = VoteBar(scale=(), vetoed=True, seen_it=False, pending_veto=False, pending_seen=True)

    assert (bar.shows_veto, bar.shows_seen, bar.vetoed, bar.seen_it) == (False, True, True, False)
    assert (VoteBar(scale=(), vetoed=True).shows_veto, VoteBar(scale=(), seen_it=True).shows_seen) == (True, True)


def test_the_note_save_in_the_pool_draws_the_closed_card_with_the_new_marks(pool):
    answer = saved(pool, veto=True, seen=True)

    assert "Vetoed by ada" in answer.text and "👁" in answer.text


def test_the_style_leaves_the_veto_pill_and_its_reason_line_to_the_box_with_no_script():
    css = (settings.BASE_DIR / "ribcage/static/theme/theme.css").read_text(encoding="utf-8")

    assert ".phase-bar:has(.vote-bar__veto-box:checked) .note-box__hint--follows" in css
    assert ".vote-bar__veto--toggle:has(.vote-bar__veto-box:checked) .vote-bar__veto-on" in css
