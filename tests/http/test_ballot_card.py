"""A tile opens as its card in VOTE: the shared card with VOTE's phase bar, each control the ballot's own write (#9, #10, #21, #122)."""

import re

import pytest
from django.conf import settings

from ribcage.ballot.models import BallotRecord
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Note
from ribcage.triggers import watched
from tests.http.test_ballot_page import HTMX, film, place, region, signed_in, walk_on_to
from tests.http.test_dtdd_credit import Tree
from tests.http.test_matched_topics import DOG, add, dtdd, vocabulary  # noqa: F401
from tests.http.test_phase import walk_to

CARD, PLACE, SEEN, REASON = "/ballot/card/", "/ballot/place/", "/ballot/seen/", "/ballot/veto-reason/"


@pytest.fixture
def ballot(voters):
    walk_to(Phase.VOTE)
    hanna = voters["Hanna"]
    return {"voters": voters, "ada": voters["ada"], "client": signed_in(voters["ada"]), "one": film(hanna, "One"), "two": film(hanna, "Two"), "three": film(hanna, "Three")}


def opened(client, suggestion, **extra):
    return client.get(CARD, {"suggestion": str(suggestion.pk), **extra}, headers=HTMX)


def bar_of(page):
    return re.search(r"data-vote-bar>(.*?)\n</div>", page, re.S)[1]


def test_a_plain_get_goes_to_the_phase_page(ballot):
    assert ballot["client"].get(CARD, {"suggestion": str(ballot["one"].pk)}).status_code == 302


def test_an_opened_card_is_the_shared_card_with_no_note_box_and_no_pencil(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")
    page = opened(ballot["client"], ballot["one"]).text

    assert f'<li class="card-item" data-suggestion="{ballot["one"].pk}"' in page and "film-card is-open" in page
    assert 'action="/note/"' not in page and 'name="text"' not in page and "runtime__pencil" not in page
    # Every note is read, the viewer's own among them, since no box holds it.
    assert "Ada wrote this." in page and "note--yours" not in page


def test_the_viewers_own_pitch_is_read_on_their_opened_card(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    page = opened(ballot["client"], own).text

    assert "Ada pitched this." in page and "note--yours" not in page


def test_the_bar_marks_the_current_score(ballot):
    place(ballot["client"], ballot["one"], 2)
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)

    assert re.findall(r'score--([a-z-]+) is-current"', bar) == ["keen"]
    assert re.findall(r'aria-pressed="true"', bar) == ['aria-pressed="true"']


def test_a_veto_replaces_the_score_with_minus_two_and_shows_the_reason_box(ballot):
    place(ballot["client"], ballot["one"], "veto")
    page = opened(ballot["client"], ballot["one"]).text
    bar = bar_of(page)

    assert "is-vetoed" in page and "−2" in bar and "data-vote-reason" in bar
    assert not re.search(r"score--(top-pick|keen|happy|dont-mind|rather-not) is-current", bar)


def test_without_a_veto_there_is_no_reason_box(ballot):
    assert "data-vote-reason" not in opened(ballot["client"], ballot["one"]).text


def test_each_score_button_posts_the_ballots_own_place_route(ballot):
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)

    assert bar.count(f'hx-post="{PLACE}"') == 6
    assert re.findall(r'"to": "([^"]+)"', bar) == ["3", "2", "1", "0", "-1", "veto"]
    assert f'hx-post="{SEEN}"' in bar


def test_placing_from_the_card_writes_as_the_drag_does_and_moves_the_card(ballot):
    answer = ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "3", "card": "1"}, headers=HTMX).text

    assert BallotRecord.objects.get(voter=ballot["ada"], suggestion=ballot["one"]).score == 3
    assert f"hx-swap-oob=\"delete:li[data-suggestion='{ballot['one'].pk}']\"" in answer
    assert "afterbegin:ul[data-place='3']" in answer and "data-scroll-here" in answer
    assert "1 of 3 scored" in answer
    assert region(ballot["client"].get("/").text, "3") == [ballot["one"].pk]


def test_a_card_moved_to_a_band_goes_after_the_tile_before_it(ballot):
    for key in ("one", "two", "three"):
        place(ballot["client"], ballot[key], 1)
    listed = region(ballot["client"].get("/").text, "1")
    answer = ballot["client"].post(PLACE, {"suggestion": str(listed[2]), "to": "1", "card": "1"}, headers=HTMX).text

    assert f"afterend:li[data-suggestion='{listed[1]}']" in answer


def test_vetoing_from_the_card_and_turning_it_off_use_the_same_write(ballot):
    ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "veto", "card": "1"}, headers=HTMX)
    assert BallotRecord.objects.get(voter=ballot["ada"]).vetoed
    ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "unsorted", "card": "1"}, headers=HTMX)

    assert BallotRecord.objects.count() == 0


def test_the_veto_pill_turns_the_veto_off_when_it_is_on_and_on_when_it_is_off(ballot):
    def veto_to():
        return re.findall(r'"to": "([^"]+)"', bar_of(opened(ballot["client"], ballot["one"]).text))[-1]

    assert veto_to() == "veto"
    place(ballot["client"], ballot["one"], "veto")
    assert veto_to() == "unsorted"


def test_the_reason_is_saved_from_the_card_as_the_note_and_answered_with_the_tile_retargeted_onto_the_card(ballot):
    place(ballot["client"], ballot["one"], "veto")
    answer = ballot["client"].post(REASON, {"suggestion": str(ballot["one"].pk), "text": "Spiders."}, headers=HTMX)

    assert Note.objects.get(suggestion=ballot["one"], author=ballot["ada"]).text == "Spiders."
    assert answer.text.lstrip().startswith('<li class="tile') and f'data-suggestion="{ballot["one"].pk}"' in answer.text
    assert "vote-reason" not in answer.text and "film-card" not in answer.text and "Saved." not in answer.text
    assert answer.headers["HX-Retarget"] == f'li.card-item[data-suggestion="{ballot["one"].pk}"]' and answer.headers["HX-Reswap"] == "outerHTML"


def test_the_cards_box_refuses_a_pitch_emptied_and_a_note_too_long_with_the_text_the_card_keeps(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    place(ballot["client"], own, "veto")

    emptied = ballot["client"].post(REASON, {"suggestion": str(own.pk), "text": " "}, headers=HTMX).text
    too_long = ballot["client"].post(REASON, {"suggestion": str(own.pk), "text": "x" * (settings.NOTE_MAX_LENGTH + 1)}, headers=HTMX).text

    assert re.search(r"<textarea[^>]*>Ada pitched this\.</textarea>", emptied) and "A suggestion needs its pitch" in emptied and "is-refusal" in emptied
    assert "a pitch holds" in too_long and "x" * 50 in too_long
    # A refusal answers the reason region, held open for another try, and Save waits on what the box was saved with (#132).
    assert emptied.lstrip().startswith('<div class="vote-reason"') and "data-unsaved" in emptied and 'data-saved="Ada pitched this."' in too_long
    assert Note.objects.get().text == "Ada pitched this."


def test_the_card_answers_a_reason_saved_empty_by_deleting_the_note_and_closing_to_the_tile(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")
    place(ballot["client"], ballot["one"], "veto")

    answer = ballot["client"].post(REASON, {"suggestion": str(ballot["one"].pk), "text": ""}, headers=HTMX).text

    assert not Note.objects.exists() and answer.lstrip().startswith("<li") and "Cleared." not in answer


def test_the_reason_box_names_what_it_was_saved_with_for_save_to_wait_on(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")
    place(ballot["client"], ballot["one"], "veto")

    shown = opened(ballot["client"], ballot["one"]).text

    assert "data-save-waits" in shown and 'data-saved="Ada wrote this."' in shown and "data-unsaved" not in shown


def test_seen_it_is_set_from_the_card_and_the_checkbox_is_answered(ballot):
    answer = ballot["client"].post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": ["0", "1"], "card": "1"}, headers=HTMX).text

    assert BallotRecord.objects.get().seen_it is True
    assert "checked" in answer and "<li" not in answer
    answer = ballot["client"].post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": ["0"], "card": "1"}, headers=HTMX).text
    assert BallotRecord.objects.count() == 0 and "checked" not in answer


def notes_of(page):
    """The card's note list as (classes, text, author line) per note, bare lines having no text."""
    found = []
    for classes, body in re.findall(r'<li class="(note[^"]*)">(.*?)</li>', page, re.S):
        full = re.search(r'<span class="note__full">(.*?)</span>', body, re.S) or re.search(r'<p class="note__text">(.*?)</p>', body, re.S)
        found.append((classes.split(), full[1] if full else "", re.search(r'<span class="note__author">(.*?)</span>', body)[1]))
    return found


def test_the_card_marks_a_vetoers_note_and_gives_a_vetoer_with_no_note_a_bare_line_and_names_none_in_the_bar(ballot):
    voters = ballot["voters"]
    Note.objects.create(suggestion=ballot["one"], author=voters["Hanna"], text="Spiders.")
    Note.objects.create(suggestion=ballot["one"], author=voters["ada"], text="Fine by me.")
    for name in ("Hanna", "Dani"):
        place(signed_in(voters[name]), ballot["one"], "veto")

    page = opened(ballot["client"], ballot["one"]).text

    assert notes_of(page) == [
        (["note", "note--pitch", "note--vetoed"], "Spiders.", "vetoed by Hanna"),
        (["note"], "Fine by me.", "ada"),
        (["note", "note--vetoed", "note--bare"], "", "Vetoed by Dani"),
    ]
    assert "film-card__label\">Vetoed by" not in page


def test_another_voters_ordinary_note_is_marked_when_its_writer_vetoes_as_the_viewer_sees_it(ballot):
    voters = ballot["voters"]
    Note.objects.create(suggestion=ballot["one"], author=voters["Dani"], text="Too scary for me.")
    place(signed_in(voters["Dani"]), ballot["one"], "veto")

    page = opened(ballot["client"], ballot["one"]).text

    assert notes_of(page) == [(["note", "note--vetoed"], "Too scary for me.", "vetoed by Dani")]


def test_a_film_nobody_vetoes_marks_nothing(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["voters"]["Hanna"], text="Spiders.")

    assert "note--vetoed" not in opened(ballot["client"], ballot["one"]).text


def test_the_viewer_who_vetoes_has_their_note_in_the_box_and_left_out_of_the_open_cards_list(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")
    place(ballot["client"], ballot["one"], "veto")

    page = opened(ballot["client"], ballot["one"]).text

    assert re.search(r"<textarea[^>]*>Ada wrote this\.</textarea>", page)
    assert notes_of(page) == [(["note", "note--yours", "note--vetoed"], "Ada wrote this.", "vetoed by ada")]
    assert "Your note on this film shows as your veto reason, and stays your note if you take the veto back." in page


def test_the_viewer_who_vetoes_with_no_note_has_an_empty_box_and_a_bare_line_the_open_card_hides(ballot):
    place(ballot["client"], ballot["one"], "veto")

    page = opened(ballot["client"], ballot["one"]).text

    assert re.search(r"<textarea[^>]*></textarea>", page)
    assert notes_of(page) == [(["note", "note--yours", "note--vetoed", "note--bare"], "", "Vetoed by ada")]


def test_a_suggester_who_vetoes_their_own_film_has_their_pitch_in_a_box_named_so(ballot):
    own = film(ballot["ada"], "Ada's own")
    Note.objects.create(suggestion=own, author=ballot["ada"], text="Ada pitched this.")
    place(ballot["client"], own, "veto")

    page = opened(ballot["client"], own).text

    assert re.search(r"<textarea[^>]*>Ada pitched this\.</textarea>", page) and "Your pitch" in page and "note-box--pitch" in page
    assert notes_of(page) == [(["note", "note--pitch", "note--yours", "note--vetoed"], "Ada pitched this.", "vetoed by ada")]


def test_a_veto_taken_back_leaves_the_note_as_a_plain_read_only_note_on_the_card(ballot):
    place(ballot["client"], ballot["one"], "veto")
    ballot["client"].post(REASON, {"suggestion": str(ballot["one"].pk), "text": "Changed my mind."})

    place(ballot["client"], ballot["one"], 2)
    page = opened(ballot["client"], ballot["one"]).text

    assert notes_of(page) == [(["note"], "Changed my mind.", "ada")]
    assert "data-vote-reason" not in page and "<textarea" not in page


def test_the_answer_to_a_veto_from_the_card_draws_the_card_with_the_box_holding_the_note(ballot):
    Note.objects.create(suggestion=ballot["one"], author=ballot["ada"], text="Ada wrote this.")

    answer = ballot["client"].post(PLACE, {"suggestion": str(ballot["one"].pk), "to": "veto", "card": "1"}, headers=HTMX).text

    assert re.search(r"<textarea[^>]*>Ada wrote this\.</textarea>", answer)


@pytest.mark.parametrize("phase", [Phase.APPROVE, Phase.SUGGEST])
def test_the_pools_cards_mark_no_veto_even_after_a_move_back(ballot, phase):
    voters = ballot["voters"]
    Note.objects.create(suggestion=ballot["one"], author=voters["Hanna"], text="Spiders.")
    place(signed_in(voters["Hanna"]), ballot["one"], "veto")
    place(signed_in(voters["Dani"]), ballot["one"], "veto")
    walk_on_to(phase)

    page = ballot["client"].get("/").text

    assert "Spiders." in page and "note--vetoed" not in page and "Vetoed by" not in page and "vetoed by" not in page


def test_the_seen_by_line_lists_other_voters_who_have_seen_it(ballot):
    voters = ballot["voters"]
    for name in ("Hanna", "Dani", "ada"):
        signed_in(voters[name]).post(SEEN, {"suggestion": str(ballot["one"].pk), "seen": "1"})

    line = re.search(r'<span class="film-card__label">Seen by</span>(.*?)</p>', opened(ballot["client"], ballot["one"]).text, re.S)[1]

    assert line.strip() == "Dani, Hanna"


def test_each_line_is_absent_when_empty(ballot):
    page = opened(ballot["client"], ballot["one"]).text

    assert "Vetoed by" not in page and "Seen by" not in page


def test_opening_one_card_closes_the_other_in_the_same_answer(ballot):
    answer = opened(ballot["client"], ballot["one"], closes=str(ballot["two"].pk)).text

    assert f"hx-swap-oob=\"outerHTML:li[data-suggestion='{ballot['two'].pk}']\"" in answer and 'class="tile' in answer


def test_the_title_closes_a_card_to_its_tile_vetoed_or_not(ballot):
    tile = opened(ballot["client"], ballot["one"], close="1").text
    assert 'class="tile' in tile
    place(ballot["client"], ballot["one"], "veto")
    assert opened(ballot["client"], ballot["one"], close="1").text == tile
    assert f'hx-get="{CARD}?suggestion={ballot["one"].pk}&amp;close=1"' in opened(ballot["client"], ballot["one"]).text


def test_a_card_for_a_film_no_longer_on_the_ballot_reloads_the_tab(ballot):
    ballot["one"].delete()
    assert opened(ballot["client"], ballot["one"]).headers.get("HX-Redirect")


def test_outside_vote_the_route_reloads_the_tab(ballot):
    walk_on_to(Phase.PICK)
    assert opened(ballot["client"], ballot["two"]).headers.get("HX-Redirect")


def test_the_viewers_own_suggestion_opens_with_no_withdraw_in_its_bar(ballot):
    own = film(ballot["ada"], "Ada's own")
    page = opened(ballot["client"], own).text

    assert "withdraw" not in page.lower()


def test_a_card_scripted_to_reload_when_its_neighbour_is_not_on_the_page():
    script = (settings.BASE_DIR / "ribcage/static/components/ballot-board.js").read_text(encoding="utf-8")

    assert re.search(r'addEventListener\("htmx:oobErrorNoTarget", reload\)', script)


def test_a_card_un_vetoed_to_the_tray_stands_where_a_reload_puts_it(voters, vocabulary):  # noqa: F811
    walk_to(Phase.VOTE)
    ada = voters["ada"]
    client = signed_in(ada)
    watched.set_ticked(ada, DOG, True)
    plain = [film(voters["Hanna"], f"Plain {number}") for number in range(6)]
    ringed = add(voters["Hanna"], "Ringed too", dog=(12, 1))
    ringed.approval = "approved"
    ringed.save()
    for each in [*plain, ringed]:
        place(client, each, "veto")
        answer = client.post(PLACE, {"suggestion": str(each.pk), "to": "unsorted", "card": "1"}, headers=HTMX).text
        tray = region(client.get("/").text, "unsorted")
        at = tray.index(each.pk)
        expected = f"afterend:li[data-suggestion='{tray[at - 1]}']" if at else "afterbegin:ul[data-place='unsorted']"
        assert expected in answer
        place(client, each, "veto")
        client.post(PLACE, {"suggestion": str(each.pk), "to": "unsorted"}, headers=HTMX)


def test_seen_it_sits_on_the_score_row_after_the_veto_pill(ballot):
    bar = bar_of(opened(ballot["client"], ballot["one"]).text)
    row = re.search(r'class="vote-bar__scores".*?\n  </div>', bar, re.S)[0]

    assert row.index("vote-bar__veto") < row.index('class="vote-seen"') and "Seen it" in row
    assert "Seen it" not in bar.replace(row, "")


def test_the_your_score_group_holds_the_six_pills_and_seen_it_stays_outside_it(ballot):
    tree = Tree(bar_of(opened(ballot["client"], ballot["one"]).text))
    groups = [node for node in tree.root.within() if node.attrs.get("role") == "group"]
    assert len(groups) == 1 and groups[0].attrs.get("aria-label") == "Your score"
    inside = [node.tag for node in groups[0].within()]

    assert inside.count("button") == 6 and "input" not in inside and "form" not in inside
    seen = tree.find(".vote-seen")
    assert len(seen) == 1 and groups[0] not in seen[0].up()
