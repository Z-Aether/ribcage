"""The Veto band: a veto is one placement that replaces the score, its tile is a band's own, a drop with no note opens the card, the reason is the voter's note and others' vetoes ride the tiles (#9, #10, #88, #120, #128)."""

import re

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Note
from ribcage.triggers import watched
from tests.http.test_ballot_page import HTMX, approved, film, place, region, signed_in, walk_on_to
from tests.http.test_matched_topics import DOG, add, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

REASON, CARD = "/ballot/veto-reason/", "/ballot/card/"


def reason(client, suggestion, text, **extra):
    return client.post(REASON, {"suggestion": str(suggestion.pk), "text": text}, **extra)


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    hanna = voters["Hanna"]
    return {"ada": voters["ada"], "client": signed_in(voters["ada"]), "one": film(hanna, "One"), "two": film(hanna, "Two"), "voters": voters}


def record(ballot, key="one"):
    return BallotRecord.objects.filter(voter=ballot["ada"], suggestion=ballot[key]).first()


def note(ballot, key="one", voter="ada"):
    """The voter's note on the film, or None."""
    found = Note.objects.filter(author=ballot["voters"][voter], suggestion=ballot[key]).first()
    return found and found.text


def box(page):
    """The text the first reason box in the page or answer holds."""
    return re.search(r"<textarea[^>]*>(.*?)</textarea>", page, re.S)[1]


def band(page):
    """The Veto band's section."""
    return re.search(r'<section class="band band--veto".*?</section>', page, re.S)[0]


def card(client, suggestion):
    """The film's card as a tile click opens it."""
    return client.get(CARD, {"suggestion": str(suggestion.pk)}, headers=HTMX).text


def drop(client, suggestion, to="veto", **extra):
    """A drag's post, as the board's script makes it."""
    return client.post("/ballot/place/", {"suggestion": str(suggestion.pk), "to": str(to), **extra}, headers=HTMX).text


def tile_of(page, suggestion):
    return re.search(rf'<li class="tile[^"]*" data-suggestion="{suggestion.pk}".*?</li>', page, re.S)


def test_a_veto_is_a_placement_that_replaces_the_score(ballot):
    place(ballot["client"], ballot["one"], 3)

    place(ballot["client"], ballot["one"], "veto")

    saved = record(ballot)
    assert (saved.score, saved.vetoed) == (None, True)


def test_a_veto_is_made_on_an_untouched_film_and_a_repeat_keeps_its_reason(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], "veto")

    assert record(ballot).vetoed and note(ballot) == "No."


def test_the_vetoed_film_is_in_the_veto_band_in_no_other_place_and_counts_as_placed(ballot):
    place(ballot["client"], ballot["one"], "veto")

    page = ballot["client"].get("/").text

    assert region(page, "veto") == [ballot["one"].pk]
    assert region(page, "unsorted") == [ballot["two"].pk]
    assert all(region(page, str(score)) == [] for score in (3, 2, 1, 0, -1))
    assert "1 of 2 scored" in page and "1 left" in page


def test_the_veto_band_is_labelled_veto_i_wont_be_in_the_room(ballot):
    heading = re.search(r'<h2 class="band__name" id="band-veto">(.*?)</h2>', ballot["client"].get("/").text, re.S)[1]

    assert re.sub(r"<[^>]+>", "", heading) == "Veto — I won't be in the room"


def test_a_vetoed_film_is_drawn_as_the_same_collapsed_tile_as_in_any_band(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    watched.set_ticked(ada, DOG, True)
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))
    Note.objects.create(suggestion=ringed, author=ada, text="My own words.")
    client = signed_in(ada)
    place(client, ringed, 2)
    scored = tile_of(client.get("/").text, ringed)[0]
    place(client, ringed, "veto")

    page = client.get("/").text
    vetoed = tile_of(page, ringed)[0]

    assert region(page, "veto") == [ringed.pk]
    # Poster, title, count pill and seen-it toggle, as in a band; and nothing that belonged to the old widened row.
    assert vetoed == scored
    assert 'class="tile has-trigger-icon"' in vetoed and "seen-toggle" in vetoed
    assert band(page).count("<li") == 1
    for gone in ("veto-row", "counts as", "<textarea", "Powered by", "dtdd", "On your list", "My own words.", "Your reason"):
        assert gone not in band(page)


def test_dragging_a_veto_out_to_a_band_takes_that_score_and_keeps_the_reason_as_the_note(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], 2)

    saved = record(ballot)
    assert (saved.score, saved.vetoed) == (2, False)
    assert note(ballot) == "No."
    assert region(ballot["client"].get("/").text, "2") == [ballot["one"].pk]


def test_dragging_a_veto_out_to_unsorted_deletes_the_empty_record_and_keeps_the_note(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "No.")

    place(ballot["client"], ballot["one"], "unsorted")

    assert not BallotRecord.objects.exists()
    assert note(ballot) == "No."
    assert ballot["one"].pk in region(ballot["client"].get("/").text, "unsorted")


def test_a_placement_answer_draws_the_tile_where_it_landed_the_same_for_a_veto_as_for_a_score(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Already said.")
    pk = ballot["one"].pk
    veto = drop(ballot["client"], ballot["one"])
    scored = drop(ballot["client"], ballot["one"], 3)

    oob = f"""<li class="tile" data-suggestion="{pk}" hx-swap-oob="outerHTML:li[data-suggestion='{pk}']" title="One">"""
    assert oob in veto and oob in scored
    assert "veto-row" not in veto and "data-vote-reason" not in veto


# What the drop opens: a film with no note yet opens its card with the reason box, closing the card open before it (#120).
def test_a_drop_into_the_veto_band_with_no_note_answers_the_open_card_with_its_reason_box(ballot):
    pk = ballot["one"].pk

    answer = drop(ballot["client"], ballot["one"])

    assert f"""<li class="card-item" data-suggestion="{pk}" data-card-open data-scroll-here data-focus-reason hx-swap-oob="outerHTML:li[data-suggestion='{pk}']">""" in answer
    assert "data-vote-reason" in answer and box(answer) == "" and "Your reason (optional)" in answer
    assert f'<li class="tile" data-suggestion="{pk}"' not in answer
    assert "1 of 2 scored" in answer
    assert record(ballot).vetoed


def test_the_opened_card_is_the_card_a_tile_click_opens_and_closes_the_card_open_before_it(ballot):
    ballot["client"].get(CARD, {"suggestion": str(ballot["two"].pk)}, headers=HTMX)
    pk, other = ballot["one"].pk, ballot["two"].pk

    answer = drop(ballot["client"], ballot["one"], closes=str(other))

    assert "film-card is-open" in answer and 'data-vote-bar' in answer
    assert f"""<li class="tile" data-suggestion="{other}" hx-swap-oob="outerHTML:li[data-suggestion='{other}']" title="Two">""" in answer
    assert answer.count("data-card-open") == 1 and f'data-suggestion="{pk}" data-card-open' in answer


def test_a_drop_naming_the_film_itself_or_none_as_the_open_card_closes_nothing(ballot):
    for closes in (str(ballot["one"].pk), "", "x", "99999"):
        place(ballot["client"], ballot["one"], "unsorted")
        answer = drop(ballot["client"], ballot["one"], closes=closes)

        assert answer.count("hx-swap-oob=\"outerHTML:li[") == 1


def test_a_drop_into_the_veto_band_with_a_note_already_opens_nothing(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Said already.")

    answer = drop(ballot["client"], ballot["one"], closes=str(ballot["two"].pk))

    assert "card-item" not in answer and "data-vote-reason" not in answer and "data-focus-reason" not in answer
    assert 'class="tile"' in answer and record(ballot).vetoed


def test_a_drop_on_the_voters_own_suggestion_opens_nothing_for_its_pitch_is_the_note(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")

    answer = drop(ballot["client"], own)

    assert "card-item" not in answer and f'<li class="tile" data-suggestion="{own.pk}"' in answer


def test_only_the_voters_own_note_counts_as_a_note_for_the_drop(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["voters"]["Dani"], text="Dani's, not Ada's.")

    assert "card-item" in drop(ballot["client"], ballot["one"])


def test_a_drop_into_any_other_band_or_the_tray_opens_nothing(ballot):
    for to in (3, 2, 1, 0, -1, "unsorted"):
        answer = drop(ballot["client"], ballot["one"], to, closes=str(ballot["two"].pk))

        assert "card-item" not in answer and "data-focus-reason" not in answer


def test_a_drop_into_the_veto_band_again_with_no_note_opens_the_card_again(ballot):
    drop(ballot["client"], ballot["one"])

    assert "data-focus-reason" in drop(ballot["client"], ballot["one"])


def test_a_veto_set_from_the_cards_bar_opens_nothing_more_and_a_plain_post_redirects(ballot):
    bar = drop(ballot["client"], ballot["one"], card="1")

    assert "data-focus-reason" not in bar and "data-scroll-here" in bar and bar.count("data-card-open") == 1
    assert place(ballot["client"], ballot["two"], "veto")["Location"] == "/"


def test_the_card_a_drop_opens_carries_the_matched_topics_in_a_credited_region_only_for_a_voter_with_a_match(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ringed = approved(add(voters["Hanna"], "Ringed", dog=(12, 1)))
    watched.set_ticked(voters["ada"], DOG, True)

    def opened_by_a_drop(voter):
        client = signed_in(voter)
        place(client, ringed, "unsorted")
        return drop(client, ringed)

    own = opened_by_a_drop(voters["ada"])
    assert "On your list" in own and "12 yes / 1 no" in own and own.count("Powered by DoesTheDogDie.com") == own.count("data-dtdd") > 0
    assert "On your list" not in opened_by_a_drop(voters["Dani"])


def test_a_reason_is_kept_as_the_note_trimmed_with_its_line_breaks_and_shown_again_on_reload(ballot):
    place(ballot["client"], ballot["one"], "veto")

    answer = reason(ballot["client"], ballot["one"], "  Too\r\nbleak.  ", headers=HTMX)

    assert note(ballot) == "Too\nbleak."
    assert answer.text.lstrip().startswith("<li") and "Saved." not in answer.text
    assert box(card(ballot["client"], ballot["one"])) == "Too\nbleak."


def test_the_box_is_pre_filled_with_the_voters_note_and_says_what_it_is(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Written in SUGGEST.")

    answer = drop(ballot["client"], ballot["one"], card="1")
    on_reload = card(ballot["client"], ballot["one"])

    for shown in (answer, on_reload):
        assert box(shown) == "Written in SUGGEST."
        assert "Your note on this film shows as your veto reason, and stays your note if you take the veto back." in shown
        assert "Your reason (optional)" in shown


def test_the_box_is_empty_where_the_voter_has_no_note(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert box(card(ballot["client"], ballot["one"])) == ""


def test_saving_the_box_changes_the_note_and_saving_it_empty_deletes_it(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Before.")
    place(ballot["client"], ballot["one"], "veto")

    reason(ballot["client"], ballot["one"], "After.")
    assert note(ballot) == "After." and Note.objects.count() == 1

    answer = reason(ballot["client"], ballot["one"], "  \r\n ", headers=HTMX)

    assert note(ballot) is None and record(ballot).vetoed
    assert "Cleared." not in answer.text


def test_a_note_written_as_a_reason_is_the_note_in_the_phases_that_write_notes(ballot):
    place(ballot["client"], ballot["one"], "veto")
    reason(ballot["client"], ballot["one"], "Mine.")
    walk_on_to(Phase.APPROVE)

    assert "Mine." in ballot["client"].get("/").text


def test_a_reason_over_the_limit_is_refused_whole_the_typed_text_is_kept_and_the_note_is_as_it_was(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Short.")
    place(ballot["client"], ballot["one"], "veto")
    typed = "x" * (settings.NOTE_MAX_LENGTH + 1)

    answer = reason(ballot["client"], ballot["one"], typed, headers=HTMX)

    assert note(ballot) == "Short."
    assert box(answer.text) == typed and "a note holds" in answer.text and "Trim it a little." in answer.text and "is-refusal" in answer.text


def test_emptying_the_box_on_the_voters_own_suggestion_is_refused_and_the_pitch_kept(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    ballot["own"] = own
    place(ballot["client"], own, "veto")

    shown = card(ballot["client"], own)
    answer = reason(ballot["client"], own, "  ", headers=HTMX)

    assert "Your pitch" in shown and box(shown) == "Ada pitched this." and "Your pitch shows as your veto reason" in shown
    assert note(ballot, "own") == "Ada pitched this."
    assert box(answer.text) == "Ada pitched this." and "A suggestion needs its pitch" in answer.text and "is-refusal" in answer.text
    reason(ballot["client"], own, "A new pitch.", headers=HTMX)
    assert note(ballot, "own") == "A new pitch."


def test_a_pitch_over_the_limit_is_refused_in_the_pitchs_wording_and_kept_as_it_was(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    place(ballot["client"], own, "veto")

    answer = reason(ballot["client"], own, "x" * (settings.NOTE_MAX_LENGTH + 1), headers=HTMX)

    assert "a pitch holds" in answer.text
    assert Note.objects.get(suggestion=own).text == "Ada pitched this."


def test_a_veto_needs_no_reason(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert region(ballot["client"].get("/").text, "veto") == [ballot["one"].pk]
    assert not Note.objects.exists()


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.PICK, Phase.RUN])
def test_a_reason_outside_vote_reloads_the_tab_and_writes_nothing(ballot, phase):
    place(ballot["client"], ballot["one"], "veto")
    walk_on_to(phase)

    answer = reason(ballot["client"], ballot["one"], "Late.", headers=HTMX)

    assert answer["HX-Redirect"] == "/"
    assert not Note.objects.exists()


def test_a_reason_on_a_film_not_vetoed_any_more_reloads_the_tab_and_writes_nothing(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Kept.")
    place(ballot["client"], ballot["one"], 2)

    assert reason(ballot["client"], ballot["one"], "Stale.", headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["two"], "None.", headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["one"], "x" * (settings.NOTE_MAX_LENGTH + 1), headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["one"], "", headers=HTMX)["HX-Redirect"] == "/"
    assert list(Note.objects.values_list("text", flat=True)) == ["Kept."]


def test_a_reason_on_a_dropped_film_or_on_none_reloads_the_tab(ballot):
    place(ballot["client"], ballot["one"], "veto")
    ballot["one"].approval = Approval.DROPPED
    ballot["one"].save()

    assert reason(ballot["client"], ballot["one"], "x", headers=HTMX)["HX-Redirect"] == "/"
    assert ballot["client"].post(REASON, {"text": "x"}, headers=HTMX)["HX-Redirect"] == "/"
    assert reason(ballot["client"], ballot["two"], "x").status_code == 302
    assert not Note.objects.exists()


def test_a_plain_reason_post_is_answered_with_the_ballot_and_the_route_answers_post_alone(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert reason(ballot["client"], ballot["one"], "Plain.")["Location"] == "/"
    assert ballot["client"].get(REASON).status_code == 405


def test_the_reason_changes_only_the_voters_own_note(ballot):
    BallotRecord.objects.create(voter=ballot["voters"]["Dani"], suggestion=ballot["one"], vetoed=True)
    Note.objects.create(suggestion=ballot["one"], author=ballot["voters"]["Dani"], text="Theirs.")
    place(ballot["client"], ballot["one"], "veto")

    reason(ballot["client"], ballot["one"], "Mine.")

    assert set(Note.objects.values_list("text", flat=True)) == {"Theirs.", "Mine."}


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

    assert ribbon(page, ballot["one"]) == (voters["Hanna"].display_name[0], "Vetoed by " + voters["Hanna"].display_name)
    assert region(page, "veto") == [ballot["one"].pk]


def test_the_voters_own_veto_shows_by_its_place_and_not_on_the_ribbon(ballot):
    place(ballot["client"], ballot["one"], "veto")

    assert "veto-ribbon" not in tile_of(ballot["client"].get("/").text, ballot["one"])[0]


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
        BallotRecord.objects.create(voter=voters["Dani" if number % 2 else "ada"], suggestion=suggestion, vetoed=True)
        Note.objects.create(suggestion=suggestion, author=voters["ada"], text="No.")

    assert queries() == small
