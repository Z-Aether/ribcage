"""Seen it: the voter's own fact about a film, set on its tile without moving it, and the board's legend (#10, #121); before VOTE it is set from the card, in test_early_marks.py (#152)."""

import re

import pytest

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note
from tests.http.test_ballot_page import HTMX, film, place, region, signed_in, walk_on_to
from tests.http.test_phase import walk_to

SEEN = "/ballot/seen/"


def seen(client, suggestion, state, **extra):
    return client.post(SEEN, {"suggestion": str(suggestion.pk), "seen": state}, **extra)


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    hanna = voters["Hanna"]
    return {"ada": voters["ada"], "client": signed_in(voters["ada"]), "one": film(hanna, "One"), "two": film(hanna, "Two"), "voters": voters}


def record(ballot, key="one", voter="ada"):
    return BallotRecord.objects.filter(voter=ballot[voter] if voter == "ada" else ballot["voters"][voter], suggestion=ballot[key]).first()


def tile_li(page, suggestion):
    return re.search(rf'<li class="tile[^"]*" data-suggestion="{suggestion.pk}".*?</li>', page, re.S)[0]


def test_seen_it_sets_and_clears_without_touching_the_score(ballot):
    place(ballot["client"], ballot["one"], 2)

    seen(ballot["client"], ballot["one"], "1")
    assert (record(ballot).score, record(ballot).seen_it) == (2, True)
    seen(ballot["client"], ballot["one"], "0")

    assert (record(ballot).score, record(ballot).seen_it) == (2, False)


def test_seen_it_sets_and_clears_without_touching_a_veto_and_its_note(ballot):
    place(ballot["client"], ballot["one"], "veto")
    ballot["client"].post("/note/", {"suggestion": str(ballot["one"].pk), "text": "No."})

    seen(ballot["client"], ballot["one"], "1")
    seen(ballot["client"], ballot["one"], "0")

    saved = record(ballot)
    assert (saved.vetoed, saved.seen_it) == (True, False)
    assert Note.objects.get(author=ballot["ada"]).text == "No."


def test_a_repeat_changes_nothing(ballot):
    seen(ballot["client"], ballot["one"], "1")
    seen(ballot["client"], ballot["one"], "1")
    assert record(ballot).seen_it is True
    seen(ballot["client"], ballot["one"], "0")
    seen(ballot["client"], ballot["one"], "0")

    assert record(ballot) is None


def test_clearing_seen_it_on_an_otherwise_empty_record_deletes_it(ballot):
    seen(ballot["client"], ballot["one"], "1")
    assert BallotRecord.objects.count() == 1

    seen(ballot["client"], ballot["one"], "0")

    assert BallotRecord.objects.count() == 0


def test_a_seen_film_never_moves_and_still_counts_as_unsorted(ballot):
    seen(ballot["client"], ballot["one"], "1")

    page = ballot["client"].get("/").text

    assert sorted(region(page, "unsorted")) == sorted([ballot["one"].pk, ballot["two"].pk])
    assert "0 of 2 scored" in page and "2 left" in page


def test_seen_it_greys_the_voters_own_tile_in_the_tray_a_band_and_the_veto_band_and_nobody_elses(ballot):
    place(ballot["client"], ballot["two"], 3)
    third = film(ballot["voters"]["Hanna"], "Three")
    place(ballot["client"], third, "veto")
    for each in (ballot["one"], ballot["two"], third):
        seen(ballot["client"], each, "1")

    page = ballot["client"].get("/").text
    other = signed_in(ballot["voters"]["Hanna"]).get("/").text

    assert page.count("is-seen-it") == 3
    assert re.search(rf'<li class="tile is-seen-it" data-suggestion="{ballot["one"].pk}"', page)
    assert re.search(rf'<li class="tile is-seen-it" data-suggestion="{ballot["two"].pk}"', page)
    assert re.search(rf'<li class="tile is-seen-it" data-suggestion="{third.pk}"', page) and region(page, "veto") == [third.pk]
    assert "is-seen-it" not in other


def test_an_answer_never_greys_a_tile_for_another_voters_seen_it(ballot):
    seen(signed_in(ballot["voters"]["Hanna"]), ballot["one"], "1")

    placed = place(ballot["client"], ballot["one"], 2, headers=HTMX).text
    cleared = seen(ballot["client"], ballot["one"], "0", headers=HTMX).text

    assert "is-seen-it" not in placed and "is-seen-it" not in cleared


def test_every_tile_carries_a_toggle_that_posts_the_state_it_would_set(ballot):
    seen(ballot["client"], ballot["one"], "1")

    page = ballot["client"].get("/").text

    assert 'aria-pressed="true"' in tile_li(page, ballot["one"]) and '"seen": "0"' in tile_li(page, ballot["one"])
    assert 'aria-pressed="false"' in tile_li(page, ballot["two"]) and '"seen": "1"' in tile_li(page, ballot["two"])


def test_the_answer_redraws_the_tile_out_of_band_vetoed_or_not(ballot):
    plain = seen(ballot["client"], ballot["one"], "1", headers=HTMX).text
    place(ballot["client"], ballot["two"], "veto")
    vetoed = seen(ballot["client"], ballot["two"], "1", headers=HTMX).text

    assert f"hx-swap-oob=\"outerHTML:li[data-suggestion='{ballot['one'].pk}']\"" in plain and "is-seen-it" in plain
    assert f"hx-swap-oob=\"outerHTML:li[data-suggestion='{ballot['two'].pk}']\"" in vetoed and "is-seen-it" in vetoed and "<textarea" not in vetoed


@pytest.mark.parametrize("phase", [Phase.PICK, Phase.RUN])
def test_a_post_after_vote_reloads_the_tab_and_writes_nothing(ballot, phase):
    walk_on_to(phase)

    answer = seen(ballot["client"], ballot["one"], "1", headers=HTMX)

    assert answer.headers["HX-Redirect"] and BallotRecord.objects.count() == 0


def test_a_stale_or_unnamed_post_reloads_and_writes_nothing(ballot):
    dropped = film(ballot["voters"]["Hanna"], "Dropped", approval="dropped")

    for post in (seen(ballot["client"], dropped, "1", headers=HTMX), seen(ballot["client"], ballot["one"], "maybe", headers=HTMX), seen(ballot["client"], ballot["one"], "", headers=HTMX)):
        assert "HX-Redirect" in post.headers
    assert BallotRecord.objects.count() == 0


def test_the_legend_reads_above_the_board_as_one_line_of_three_marks_then_the_hidden_scores(ballot):
    page = ballot["client"].get("/").text

    legend = page.index('class="ballot-legend"')
    assert legend < page.index("data-board")
    line = page[legend : page.index("</p>", legend)]
    assert "lime ring" in line and "greyed" in line and "red ribbon" in line
    assert line.count("ballot-legend__mark ") == 3 and "Scores stay hidden" in line
