"""Adding films to the timetable by hand, selecting a box and removing it, and a dropped film's box (#36, #137)."""

import html
import re

import pytest
from django.test import Client

from ribcage.ballot import placing
from ribcage.ballot.placing import VETO
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable import laying
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR, ADD, REMOVE = "/console/pick/", "/console/pick/anchor/", "/console/pick/add/", "/console/pick/remove/"
APPROVAL = "/console/films/approval/"


@pytest.fixture
def hand(admin, voters):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb_id, title, runtime in [(431, "Cube", 90), (1091, "The Thing", 109), (420634, "Terrifier", 85), (1, "Alien", 117)]:
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb_id, title, runtime=runtime), "A pitch.")
    Suggestion.objects.filter(pk__in=[each.pk for each in films.values()]).update(approval=Approval.APPROVED)
    return {"admin": admin, "voters": voters, **films}


def listed(page):
    section = re.search(r'<section class="candidates".*?</section>', page, re.S)[0]
    return [html.unescape(title) for title in re.findall(r'<span class="candidate__title">(.*?)</span>', section)], section


def test_the_list_holds_the_approved_films_not_on_the_timetable_in_slate_order_with_its_count(hand):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})
    placing.place(hand["voters"]["Dani"], hand["Terrifier"], VETO)
    placing.place(hand["voters"]["Hanna"], hand["Alien"], 3)

    titles, section = listed(hand["admin"].get(PICK).text)

    assert titles == ["Alien", "The Thing", "Terrifier"]
    assert "Approved, not in the plan" in section and '<span class="candidates__count">3</span>' in section


def test_a_dropped_or_undecided_film_never_appears(hand):
    Suggestion.objects.filter(pk=hand["Cube"].pk).update(approval=Approval.DROPPED)
    Suggestion.objects.filter(pk=hand["Alien"].pk).update(approval=Approval.UNDECIDED)

    titles, _ = listed(hand["admin"].get(PICK).text)

    assert titles == ["Terrifier", "The Thing"]


def test_a_plus_lays_the_first_box_at_the_anchor_and_selects_it(hand):
    response = hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})

    box = Box.objects.get()
    assert (box.suggestion_id, box.start) == (hand["Cube"].pk, 0)
    assert response.headers["Location"] == f"{PICK}?box={box.pk}"


def test_a_plus_lays_the_next_box_flush_after_the_last_on_the_five_minute_grid(hand):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})
    hand["admin"].post(ADD, {"suggestion": hand["The Thing"].pk})
    hand["admin"].post(ADD, {"suggestion": hand["Terrifier"].pk})

    # Cube ends at 90, which is on the grid; The Thing ends at 90 + 109 = 199, so the next starts at 200.
    assert list(Box.objects.order_by("start").values_list("suggestion__title", "start")) == [("Cube", 0), ("The Thing", 90), ("Terrifier", 200)]


def test_the_last_box_is_the_one_that_ends_last_and_a_labelled_box_counts(hand):
    Box.objects.create(label="Dinner", length=45, start=1000)
    Box.objects.create(suggestion=hand["Cube"], start=0)

    assert laying.next_start() == 1045
    assert laying.lay_film(hand["Alien"].pk).start == 1045


def test_a_plus_for_a_film_already_placed_or_dropped_since_changes_nothing(hand):
    admin = hand["admin"]
    admin.post(ADD, {"suggestion": hand["Cube"].pk})
    Suggestion.objects.filter(pk=hand["Alien"].pk).update(approval=Approval.DROPPED)

    again = admin.post(ADD, {"suggestion": hand["Cube"].pk})
    dropped = admin.post(ADD, {"suggestion": hand["Alien"].pk})
    nonsense = admin.post(ADD, {"suggestion": "abc"})

    assert Box.objects.count() == 1
    assert [each.headers["Location"] for each in (again, dropped, nonsense)] == [PICK] * 3


def test_with_no_anchor_the_list_shows_with_its_plus_unavailable_and_a_post_changes_nothing(admin, voters):
    film = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "A pitch.")
    Suggestion.objects.filter(pk=film.pk).update(approval=Approval.APPROVED)

    page = admin.get(PICK).text
    admin.post(ADD, {"suggestion": film.pk})

    titles, section = listed(page)
    assert titles == ["Cube"] and "disabled" in section
    assert Box.objects.count() == 0


def test_a_click_selects_a_box_through_the_address_and_shows_its_panel(hand):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})
    box = laying.lay_film(hand["The Thing"].pk)
    placing.place(hand["voters"]["Dani"], hand["The Thing"], VETO)

    page = hand["admin"].get(f"{PICK}?box={box.pk}").text

    assert f'href="{PICK}?box={box.pk}" aria-current="true"' in page
    assert page.count("track__slot is-selected") == 1
    panel = re.search(r'<section class="box-panel".*?</section>', page, re.S)[0]
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", panel)).split())
    assert "The Thing" in text and "Starts Sat 19:30 → 21:19" in text and "Runtime 109 min" in text
    assert "Vetoed by Dani" in text and "Dropped" not in text and "Remove from the plan" in text


@pytest.mark.parametrize("chosen", ["", "0", "999999", "abc", "-1", "1" * 30])
def test_a_selection_naming_no_box_is_no_selection(hand, chosen):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})

    page = hand["admin"].get(f"{PICK}?box={chosen}").text

    assert 'class="box-panel"' not in page and "track__slot is-selected" not in page


def test_remove_from_the_plan_takes_the_box_off_and_moves_no_other(hand):
    admin = hand["admin"]
    first, middle, last = (laying.lay_film(hand[title].pk) for title in ("Cube", "The Thing", "Terrifier"))
    before = {box.pk: box.start for box in Box.objects.exclude(pk=middle.pk)}

    response = admin.post(REMOVE, {"box": middle.pk})

    assert response.headers["Location"] == PICK
    assert {box.pk: box.start for box in Box.objects.all()} == before
    assert "The Thing" in listed(admin.get(PICK).text)[0]
    assert admin.post(REMOVE, {"box": middle.pk}).status_code == 302
    assert admin.post(REMOVE, {"box": "x"}).status_code == 302


def test_dropping_a_placed_film_keeps_its_box_marked_and_reapproving_changes_only_the_mark(hand):
    admin = hand["admin"]
    box = laying.lay_film(hand["Cube"].pk)

    admin.post(APPROVAL, {"suggestion": hand["Cube"].pk, "from_approval": "approved", "to_approval": "dropped"})

    assert Box.objects.get().start == 0
    page = admin.get(f"{PICK}?box={box.pk}").text
    assert "box--dropped" in page and "Dropped" in page
    assert "Cube" not in listed(page)[0]

    admin.post(APPROVAL, {"suggestion": hand["Cube"].pk, "from_approval": "dropped", "to_approval": "approved"})

    page = admin.get(f"{PICK}?box={box.pk}").text
    assert "box--dropped" not in page and Box.objects.get().start == 0


def test_the_hand_edits_need_the_admin(hand):
    assert Client().post(ADD, {"suggestion": hand["Cube"].pk}).status_code in (302, 403)
    assert Box.objects.count() == 0


def test_the_panel_names_the_end_day_only_when_it_is_another_day(hand):
    hand["admin"].post(ANCHOR, {"anchor": "2026-11-07T23:00"})
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})
    box = laying.lay_film(hand["The Thing"].pk)

    page = hand["admin"].get(f"{PICK}?box={box.pk}").text

    assert "Starts Sat 00:30" not in page and "Starts Sun 00:30 → 02:19" in " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def test_the_track_and_the_split_keep_their_scroll_across_a_reload(hand):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})

    page = hand["admin"].get(PICK).text

    assert 'class="track-frame" data-keeps-scroll' in page and 'class="pick-split" data-keeps-scroll' in page
    assert page.count('data-lands-on="/console/pick/"') >= 1


def test_the_remove_form_in_the_panel_names_where_it_lands(hand):
    hand["admin"].post(ADD, {"suggestion": hand["Cube"].pk})
    box = laying.lay_film(hand["The Thing"].pk)

    page = hand["admin"].get(f"{PICK}?box={box.pk}").text

    assert re.search(r'<form[^>]*pick/remove/[^>]*data-lands-on="/console/pick/"', page)
