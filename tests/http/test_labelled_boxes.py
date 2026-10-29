"""Labelled boxes: + Break, the labelled box's panel, its refusals and Remove (#22, #138)."""

import html
import re

import pytest

from ribcage.timetable import labelling, laying
from ribcage.timetable.models import Box

PICK, ANCHOR, BREAK, SAVE, REMOVE = "/console/pick/", "/console/pick/anchor/", "/console/pick/break/", "/console/pick/box/", "/console/pick/remove/"


@pytest.fixture
def evening(admin):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    return admin


def text_of(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def test_a_break_on_an_empty_timetable_is_thirty_minutes_at_the_anchor_and_selected(evening):
    response = evening.post(BREAK)

    box = Box.objects.get()
    assert (box.label, box.length, box.start, box.suggestion_id) == ("Break", 30, 0, None)
    assert response.headers["Location"] == f"{PICK}?box={box.pk}"


def test_a_break_lands_flush_after_the_last_box_on_the_grid(evening):
    Box.objects.create(label="Dinner", length=47, start=10)

    evening.post(BREAK)

    assert Box.objects.order_by("start").last().start == 60


def test_a_break_needs_the_anchor_and_its_button_is_unavailable_without_it(admin):
    page = admin.get(PICK).text
    admin.post(BREAK)

    assert re.search(r"<button[^>]*disabled[^>]*>\+ Break", page)
    assert Box.objects.count() == 0


def test_the_break_button_is_offered_on_an_empty_timetable_and_on_the_track(evening):
    assert "+ Break" in evening.get(PICK).text
    evening.post(BREAK)
    assert re.search(r'<form[^>]*pick/break/[^>]*data-lands-on="/console/pick/"', evening.get(PICK).text)


def test_a_labelled_box_shows_its_panel(evening):
    box = Box.objects.create(label="Dinner", length=45, start=100)

    page = evening.get(f"{PICK}?box={box.pk}").text

    panel = re.search(r'<section class="box-panel".*?</section>', page, re.S)[0]
    assert 'name="label" value="Dinner"' in panel and 'name="length" value="45"' in panel
    assert "Starts Sat 19:40 → 20:25" in text_of(panel)
    assert re.search(r'<form[^>]*pick/box/[^>]*data-lands-on="/console/pick/"', panel)


def test_save_keeps_the_label_and_the_length_together_and_selects_the_box(evening):
    box = Box.objects.create(label="Break", length=30, start=0)

    response = evening.post(SAVE, {"box": box.pk, "label": "  Pizza arrives ", "length": "45"})

    box.refresh_from_db()
    assert (box.label, box.length, box.start) == ("Pizza arrives", 45, 0)
    assert response.headers["Location"] == f"{PICK}?box={box.pk}"


def test_a_longer_box_overlaps_its_neighbour_and_moves_nothing(evening):
    first = Box.objects.create(label="Break", length=30, start=0)
    second = Box.objects.create(label="Dinner", length=45, start=30)

    evening.post(SAVE, {"box": first.pk, "label": "Break", "length": "60"})

    second.refresh_from_db()
    assert second.start == 30
    assert "1 overlap" in evening.get(PICK).text


@pytest.mark.parametrize(
    ("label", "length", "which", "says"),
    [("", "30", "label", labelling.NO_LABEL), ("   ", "30", "label", labelling.NO_LABEL), ("x" * 41, "30", "label", labelling.LONG_LABEL),
     ("Tea", "", "length", labelling.EMPTY), ("Tea", "4", "length", labelling.TOO_SHORT), ("Tea", "0", "length", labelling.TOO_SHORT),
     ("Tea", "-5", "length", labelling.TOO_SHORT), ("Tea", "32", "length", labelling.NOT_IN_STEPS), ("Tea", "2.5", "length", labelling.NOT_WHOLE_MINUTES),
     ("Tea", "1h", "length", labelling.NOT_WHOLE_MINUTES), ("Tea", "9" * 40, "length", labelling.TOO_LONG)],
)
def test_a_refused_save_saves_nothing_and_keeps_the_typing(evening, label, length, which, says):
    box = Box.objects.create(label="Break", length=30, start=0)

    response = evening.post(SAVE, {"box": box.pk, "label": label, "length": length})

    box.refresh_from_db()
    assert (box.label, box.length) == ("Break", 30)
    assert response.status_code == 200
    page = response.text
    assert f'id="box-{which}-refusal"' in page
    assert says in text_of(page)
    assert f'name="label" value="{label}"' in page and f'name="length" value="{length}"' in page
    assert "track__slot is-selected" in page


def test_a_label_of_exactly_forty_characters_is_kept(evening):
    box = Box.objects.create(label="Break", length=30, start=0)

    evening.post(SAVE, {"box": box.pk, "label": "x" * 40, "length": "30"})

    box.refresh_from_db()
    assert box.label == "x" * 40


def test_a_save_for_a_film_box_or_a_box_gone_changes_nothing(evening, voters):
    from ribcage.suggestions.models import Approval, Suggestion
    from tests.films import a_tmdb_film

    film = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "A pitch.")
    Suggestion.objects.filter(pk=film.pk).update(approval=Approval.APPROVED)
    placed = laying.lay_film(film.pk)

    for box in (placed.pk, 9999, "x"):
        assert evening.post(SAVE, {"box": box, "label": "Tea", "length": "30"}).status_code == 302

    placed.refresh_from_db()
    assert (placed.label, placed.length) == ("", None)


def test_remove_takes_a_labelled_box_off_and_moves_no_other(evening):
    first = Box.objects.create(label="Break", length=30, start=0)
    second = Box.objects.create(label="Dinner", length=45, start=30)
    third = Box.objects.create(label="Tea", length=15, start=75)

    evening.post(REMOVE, {"box": second.pk})

    assert dict(Box.objects.values_list("pk", "start")) == {first.pk: 0, third.pk: 75}


def test_the_new_posts_need_the_admin(db):
    from django.test import Client

    Box.objects.create(label="Break", length=30, start=0)
    client = Client()
    for address in (BREAK, SAVE):
        assert client.post(address, {"box": 1, "label": "x", "length": "5"}).status_code in (302, 403)
    assert Box.objects.get().label == "Break"
