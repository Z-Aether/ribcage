"""The Timetable sub-tab's track: the evening in TIME_ZONE, the clocks, the marker, vetoes, the dropped mark and a flat query count (#22, #136)."""

import html
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ribcage.ballot import placing
from ribcage.ballot.placing import VETO
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR, BUDGET = "/console/pick/", "/console/pick/anchor/", "/console/pick/budget/"


@pytest.fixture
def evening(admin, voters):
    """Two films and a Dinner from 18:00 with a 9 hour budget: 3h19m of screen time."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    admin.post(BUDGET, {"hours": "9", "minutes": ""})
    cube = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")
    thing = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    Suggestion.objects.filter(pk__in=[cube.pk, thing.pk]).update(approval=Approval.APPROVED)
    Box.objects.create(suggestion=cube, start=0)
    Box.objects.create(label="Dinner", length=45, start=100)
    Box.objects.create(suggestion=thing, start=160)
    return {"admin": admin, "voters": voters, "cube": cube, "thing": thing}


def boxes_on(page):
    return re.findall(r'<div class="box [^"]*"[^>]*>.*?</div>(?=\s*</a>)', page, re.S)


def text_of(fragment):
    # Without the poster slot, whose title card repeats the title of a film that has no poster.
    fragment = re.sub(r'<span class="box__poster">.*?</span></span>', "", fragment, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def test_the_track_draws_the_seeded_evenings_times_in_the_deployments_time_zone(evening, settings):
    # The anchor was set at 18:00 UTC; the page reads it in Budapest, an hour ahead in November.
    settings.TIME_ZONE = "Europe/Budapest"
    page = evening["admin"].get(PICK).text

    texts = [text_of(box) for box in boxes_on(page)]
    assert texts == ["Cube 19:00–20:30 1h30m", "Dinner 20:40–21:25 45m", "The Thing 21:40–23:29 1h49m"]
    assert "Evening Sat 19:00 → Sat 23:29" in text_of(page)


def test_the_tool_row_gives_screen_time_against_the_budget_and_the_evening_line(evening):
    page = text_of(evening["admin"].get(PICK).text)

    assert "Screen time 3h19m of 9h budget" in page
    assert "5h41m to spare" in page
    assert "Evening Sat 18:00 → Sat 22:29 · 4h29m elapsed" in page
    assert "overlap" not in page.split("Evening")[1].split("Compare")[0]


def test_a_budget_below_screen_time_says_over_and_marks_the_minute_inside_a_film(evening):
    evening["admin"].post(BUDGET, {"hours": "3", "minutes": ""})

    page = evening["admin"].get(PICK).text

    assert "Screen time 3h19m of 3h budget" in text_of(page)
    assert "19m over" in page
    assert 'class="track__budget' in page and ">budget 3h<" in page


def test_no_budget_reads_no_budget_set_and_draws_no_marker(evening):
    evening["admin"].post(BUDGET, {"hours": "", "minutes": ""})

    page = evening["admin"].get(PICK).text

    assert "Screen time 3h19m · no budget set" in text_of(page)
    assert 'class="track__budget' not in page and 'role="meter"' not in page


def test_a_budget_met_with_room_draws_no_marker(evening):
    assert 'class="track__budget' not in evening["admin"].get(PICK).text


def test_overlapping_boxes_are_flagged_with_a_band_and_a_count(evening):
    Box.objects.filter(label="Dinner").update(start=80)

    page = evening["admin"].get(PICK).text

    assert page.count('class="track__overlap"') == 1
    assert page.count("box--overlapping") == 2
    assert "1 overlap<" in page


def test_a_vetoed_film_carries_the_vetoers_initials_over_the_timetables_own_films_whatever_its_approval(evening):
    voters = evening["voters"]
    placing.place(voters["Hanna"], evening["cube"], VETO)
    placing.place(voters["ada"], evening["cube"], VETO)
    Suggestion.objects.filter(pk=evening["cube"].pk).update(approval=Approval.DROPPED)

    page = evening["admin"].get(PICK).text

    assert re.findall(r'<span class="box__vetoes" title="([^"]*)">(\w+)</span>', page) == [("Vetoed by Hanna, ada", "HA")]


def test_a_dropped_films_box_stays_where_it_is_and_carries_the_mark(evening):
    Suggestion.objects.filter(pk=evening["thing"].pk).update(approval=Approval.DROPPED)

    page = evening["admin"].get(PICK).text

    thing = next(box for box in boxes_on(page) if "The Thing" in box)
    assert "box--dropped" in thing and "dropped</span>" in thing
    assert [("box--dropped" in box) for box in boxes_on(page)] == [False, False, True]
    assert "20:40–22:29" in text_of(thing)


def test_an_undecided_films_box_has_no_mark(evening):
    Suggestion.objects.filter(pk=evening["thing"].pk).update(approval=Approval.UNDECIDED)

    assert "dropped" not in evening["admin"].get(PICK).text.replace("box--dropped", "")


def test_the_track_is_on_the_timetable_sub_tab_only(evening):
    assert 'class="track"' in evening["admin"].get(PICK).text
    assert 'class="track"' not in evening["admin"].get("/console/pick/compare/").text


def test_no_boxes_leaves_the_empty_line_and_no_track(admin):
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})

    page = admin.get(PICK).text

    assert "Nothing on the timetable yet." in page and 'class="track"' not in page


def test_the_tabs_query_count_does_not_grow_with_the_timetable(evening):
    admin = evening["admin"]

    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(PICK)
        return len(captured)

    before = queries()
    for index in range(8):
        film = Suggestion.objects.suggest(evening["voters"]["Dani"], a_tmdb_film(9000 + index, f"Film {index}", runtime=90), "")
        placing.place(evening["voters"]["Hanna"], film, VETO)
        Box.objects.create(suggestion=film, start=300 + index * 100)
        Box.objects.create(label=f"Break {index}", length=10, start=200 + index * 100)

    assert queries() == before
