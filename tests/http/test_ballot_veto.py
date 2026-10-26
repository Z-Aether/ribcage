"""The Veto band: a veto is one placement that replaces the score, its widened row and its reason, and others' vetoes on the tiles (#9, #10, #88, #120)."""

import re

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval
from ribcage.triggers import watched
from tests.http.test_ballot_page import HTMX, approved, film, place, region, signed_in, walk_on_to
from tests.http.test_matched_topics import DOG, add, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

REASON = "/ballot/veto-reason/"


def reason(client, suggestion, text, **extra):
    return client.post(REASON, {"suggestion": str(suggestion.pk), "text": text}, **extra)


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    hanna = voters["Hanna"]
    return {"ada": voters["ada"], "client": signed_in(voters["ada"]), "one": film(hanna, "One"), "two": film(hanna, "Two"), "voters": voters}


def record(ballot, key="one"):
    return BallotRecord.objects.filter(voter=ballot["ada"], suggestion=ballot[key]).first()


def row(page, suggestion):
    return re.search(rf'<li class="veto-row" data-suggestion="{suggestion.pk}".*?</div>\s*</li>', page, re.S)


def tile_of(page, suggestion):
    return re.search(rf'<li class="tile[^"]*" data-suggestion="{suggestion.pk}".*?</li>', page, re.S)


def test_a_veto_is_a_placement_that_replaces_the_score(ballot):
    place(ballot["client"], ballot["one"], 3)

    place(ballot["client"], ballot["one"], "veto")

    saved = record(ballot)
    assert (saved.score, saved.vetoed, saved.veto_reason) == (None, True, None)


def test_a_veto_is_made_on_an_untouched_film_and_a_repeat_keeps_its_reason(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], "veto")

    assert (record(ballot).vetoed, record(ballot).veto_reason) == (True, "No.")


def test_the_vetoed_film_is_in_the_veto_band_as_a_row_and_in_no_other_place_and_counts_as_placed(ballot):
    place(ballot["client"], ballot["one"], "veto")

    page = ballot["client"].get("/").text

    assert row(page, ballot["one"]) and region(page, "veto") == [ballot["one"].pk]
    assert region(page, "unsorted") == [ballot["two"].pk]
    assert all(region(page, str(score)) == [] for score in (3, 2, 1, 0, -1))
    assert "1 of 2 scored" in page and "1 left" in page
    assert "counts as −2 for you, everyone can see it" in row(page, ballot["one"])[0]
    assert '<div class="tile" title="One">' in row(page, ballot["one"])[0]


def test_dragging_a_veto_out_to_a_band_takes_that_score_and_clears_the_reason(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], 2)

    saved = record(ballot)
    assert (saved.score, saved.vetoed, saved.veto_reason) == (2, False, None)
    assert region(ballot["client"].get("/").text, "2") == [ballot["one"].pk]


def test_dragging_a_veto_out_to_unsorted_leaves_it_with_none_and_deletes_the_empty_record(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], "unsorted")

    assert not BallotRecord.objects.exists()
    assert ballot["one"].pk in region(ballot["client"].get("/").text, "unsorted")


def test_a_placement_answer_draws_the_tile_where_it_landed_as_a_row_for_a_veto_and_a_tile_otherwise(ballot):
    pk = ballot["one"].pk
    veto = place(ballot["client"], ballot["one"], "veto", headers=HTMX).text
    scored = place(ballot["client"], ballot["one"], 3, headers=HTMX).text

    assert f"""<li class="veto-row" data-suggestion="{pk}" hx-swap-oob="outerHTML:li[data-suggestion='{pk}']">""" in veto
    assert '<li class="veto-row"' not in scored
    assert f"""<li class="tile" data-suggestion="{pk}" hx-swap-oob="outerHTML:li[data-suggestion='{pk}']" title="One">""" in scored


def test_a_reason_is_kept_trimmed_with_its_line_breaks_and_shown_again_on_reload(ballot):
    place(ballot["client"], ballot["one"], "veto")

    answer = reason(ballot["client"], ballot["one"], "  Too\r\nbleak.  ", headers=HTMX)

    assert record(ballot).veto_reason == "Too\nbleak."
    assert "Saved." in answer.text
    assert "Too\nbleak." in row(ballot["client"].get("/").text, ballot["one"])[0]


def test_a_reason_over_the_limit_is_refused_whole_and_the_typed_text_is_kept(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "Short.")
    typed = "x" * (settings.NOTE_MAX_LENGTH + 1)

    answer = reason(ballot["client"], ballot["one"], typed, headers=HTMX)

    assert record(ballot).veto_reason == "Short."
    assert typed in answer.text and "Trim it a little." in answer.text and "is-refusal" in answer.text


def test_an_empty_reason_clears_it_and_is_stored_as_none(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    answer = reason(ballot["client"], ballot["one"], "  \r\n ", headers=HTMX)

    assert record(ballot).veto_reason is None and record(ballot).vetoed
    assert "Cleared." in answer.text


def test_a_veto_needs_no_reason(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert row(ballot["client"].get("/").text, ballot["one"])


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.PICK, Phase.RUN])
def test_a_reason_outside_vote_reloads_the_tab_and_writes_nothing(ballot, phase):
    place(ballot["client"], ballot["one"], "veto")
    walk_on_to(phase)

    answer = reason(ballot["client"], ballot["one"], "Late.", headers=HTMX)

    assert answer["HX-Redirect"] == "/"
    assert record(ballot).veto_reason is None


def test_a_reason_on_a_film_not_vetoed_any_more_reloads_the_tab_and_writes_nothing(ballot):
    place(ballot["client"], ballot["one"], 2)

    assert reason(ballot["client"], ballot["one"], "Stale.", headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["two"], "None.", headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["one"], "x" * (settings.NOTE_MAX_LENGTH + 1), headers=HTMX)["HX-Redirect"] == "/"
    assert list(BallotRecord.objects.values_list("veto_reason", flat=True)) == [None]


def test_a_reason_on_a_dropped_film_or_on_none_reloads_the_tab(ballot):
    place(ballot["client"], ballot["one"], "veto")
    ballot["one"].approval = Approval.DROPPED
    ballot["one"].save()

    assert reason(ballot["client"], ballot["one"], "x", headers=HTMX)["HX-Redirect"] == "/"
    assert ballot["client"].post(REASON, {"text": "x"}, headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["two"], "x").status_code == 302


def test_a_plain_reason_post_is_answered_with_the_ballot_and_the_route_answers_post_alone(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert reason(ballot["client"], ballot["one"], "Plain.")["Location"] == "/"
    assert ballot["client"].get(REASON).status_code == 405


def test_the_reason_changes_only_the_voters_own_veto(ballot):
    BallotRecord.objects.create(voter=ballot["voters"]["Dani"], suggestion=ballot["one"], vetoed=True, veto_reason="Theirs.")
    place(ballot["client"], ballot["one"], "veto")

    reason(ballot["client"], ballot["one"], "Mine.")

    assert set(BallotRecord.objects.values_list("veto_reason", flat=True)) == {"Theirs.", "Mine."}


def test_the_row_carries_the_matched_topics_in_a_credited_region_only_for_a_voter_with_a_match(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))
    watched.set_ticked(voters["ada"], DOG, True)
    for name in ("ada", "Dani"):
        BallotRecord.objects.create(voter=voters[name], suggestion=ringed, vetoed=True)

    def widened(voter):
        return row(signed_in(voter).get("/").text, ringed)[0]

    own = widened(voters["ada"])
    assert re.search(r'<div class="veto-row__matched" data-dtdd>.*dog death.*12 yes / 1 no.*Powered by DoesTheDogDie.com.*?</div>', own, re.S)
    other = widened(voters["Dani"])
    assert "data-dtdd" not in other and "Powered by" not in other and "On your list" not in other
    watched.stop_caring(voters["ada"])
    assert "Powered by" not in widened(voters["ada"])


def test_a_film_the_voter_watches_nothing_for_shows_no_matched_block_in_its_row(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert "Powered by" not in row(ballot["client"].get("/").text, ballot["one"])[0]


def test_the_reasons_answer_carries_the_row_with_its_matched_topics_and_credit(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))
    watched.set_ticked(voters["ada"], DOG, True)
    client = signed_in(voters["ada"])
    place(client, ringed, "veto")

    answer = reason(client, ringed, "Why.", headers=HTMX).text

    assert "12 yes / 1 no" in answer and "Powered by DoesTheDogDie.com" in answer and "data-dtdd" in answer


def ribbon(page, suggestion):
    tile = tile_of(page, suggestion)[0]
    found = re.search(r'<span class="veto-ribbon"(?: title="([^"]*)")?>([^<]*)</span>', tile)
    return None if found is None else (found[2], found[1])


def test_another_voters_tile_shows_the_vetoers_initials_and_names(ballot):
    voters = ballot["voters"]
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=ballot["one"], vetoed=True)
    BallotRecord.objects.create(voter=voters["Hanna"], suggestion=ballot["one"], vetoed=True)

    names = sorted([voters["Dani"].display_name, voters["Hanna"].display_name])
    assert ribbon(ballot["client"].get("/").text, ballot["one"]) == ("".join(name[0] for name in names), "Vetoed by " + ", ".join(names))
    assert ribbon(ballot["client"].get("/").text, ballot["two"]) is None


def test_the_vetoers_own_ballot_shows_no_ribbon_for_their_own_veto_and_shows_the_others(ballot):
    voters = ballot["voters"]
    BallotRecord.objects.create(voter=voters["Dani"], suggestion=ballot["one"], vetoed=True)
    BallotRecord.objects.create(voter=voters["Hanna"], suggestion=ballot["one"], vetoed=True)

    page = signed_in(voters["Dani"]).get("/").text

    assert tile_of(page, ballot["one"]) is None
    assert re.search(r'veto-ribbon"[^>]*>' + voters["Hanna"].display_name[0] + "<", row(page, ballot["one"])[0])
    assert "Vetoed by " + voters["Hanna"].display_name in row(page, ballot["one"])[0]


def test_the_voters_own_veto_shows_by_its_place_and_not_on_the_ribbon(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert "veto-ribbon" not in row(ballot["client"].get("/").text, ballot["one"])[0]


def test_a_veto_on_a_film_in_a_band_marks_it_for_others_wherever_it_sits(ballot):
    BallotRecord.objects.create(voter=ballot["voters"]["Dani"], suggestion=ballot["one"], vetoed=True)
    place(ballot["client"], ballot["one"], 3)

    assert ribbon(ballot["client"].get("/").text, ballot["one"])[0] == ballot["voters"]["Dani"].display_name[0]


def test_the_veto_band_lists_only_the_viewers_own_vetoes(ballot):
    BallotRecord.objects.create(voter=ballot["voters"]["Dani"], suggestion=ballot["one"], vetoed=True)

    assert region(ballot["client"].get("/").text, "veto") == []


def test_the_pages_query_count_does_not_grow_with_the_vetoes(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    watched.set_ticked(ada, DOG, True)

    def queries():
        client = signed_in(ada)
        with CaptureQueriesContext(connection) as captured:
            client.get("/")
        return len(captured)

    first = approved(add(voters["Hanna"], "First", dog=(12, 1)))
    BallotRecord.objects.create(voter=ada, suggestion=first, vetoed=True)
    small = queries()
    for number in range(8):
        suggestion = approved(add(voters["Hanna"], f"Later {number}", dog=(12, 1)))
        BallotRecord.objects.create(voter=voters["Dani" if number % 2 else "ada"], suggestion=suggestion, vetoed=True, veto_reason="No.")

    assert queries() == small
