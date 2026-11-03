"""RUN's page: the evening, the published timetable fitted to one screen, with none of the admin's readouts (#155)."""

import html
import re
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from ribcage.ballot import placing
from ribcage.ballot.placing import VETO
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box, Timetable
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to


def reader(voter):
    client = Client()
    client.force_login(voter)
    return client


@pytest.fixture
def running(voters):
    """RUN with a timetable from 18:00 UTC: Cube, Dinner, a dropped The Thing vetoed by Dani, and a veto-free film."""
    walk_to(Phase.PICK)
    Timetable.objects.create(pk=1, anchor="2026-11-07T18:00:00Z", budget=9 * 60)
    films = {}
    for tmdb_id, title, runtime in ((431, "Cube", 90), (1091, "The Thing", 109), (8413, "Event Horizon", 96)):
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb_id, title, runtime=runtime), "Pitch.")
    Suggestion.objects.filter(pk=films["Cube"].pk).update(approval=Approval.APPROVED)
    Suggestion.objects.filter(pk=films["Event Horizon"].pk).update(approval=Approval.APPROVED)
    Suggestion.objects.filter(pk=films["The Thing"].pk).update(approval=Approval.DROPPED)
    placing.place(voters["Dani"], films["The Thing"], VETO)
    Box.objects.create(suggestion=films["Cube"], start=0)
    Box.objects.create(label="Dinner", length=45, start=100, flexible=True)
    Box.objects.create(suggestion=films["The Thing"], start=160, flexible=False)
    Box.objects.create(suggestion=films["Event Horizon"], start=280)
    move(Phase.PICK, Phase.RUN)
    return {"ada": voters["ada"], "voters": voters, "films": films}


def slots_of(page):
    return re.findall(r'<div class="evening__slot .*?<span class="evening__progress".*?</div>', page, re.S)


def text_of(fragment):
    fragment = re.sub(r'<span class="evening__status".*?</span>', "", fragment, flags=re.S)
    fragment = re.sub(r'<span class="box__poster">.*?</span></span>', "", fragment, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def test_every_box_is_shown_with_its_times(running, settings):
    settings.TIME_ZONE = "Europe/Budapest"

    page = reader(running["ada"]).get("/").text

    assert [text_of(slot) for slot in slots_of(page)] == [
        "Cube 19:00–20:30 1h30m",
        "Dinner 20:40–21:25 45m",
        "The Thing 21:40–23:29 1h49m",
        "Event Horizon 23:40–01:16 1h36m",
    ]


def test_the_evening_is_a_region_of_its_own_carrying_its_span_and_each_boxs_instants(running):
    page = reader(running["ada"]).get("/").text

    region = re.search(r'<section class="evening" id="evening"[^>]*>', page)[0]
    assert 'data-evening-start="2026-11-07T18:00:00+00:00"' in region
    assert 'data-evening-end="2026-11-08T00:16:00+00:00"' in region
    assert 'data-evening-minutes="376"' in region
    assert 'data-start="2026-11-07T18:00:00+00:00" data-end="2026-11-07T19:30:00+00:00"' in page


def test_none_of_the_admins_readouts_are_drawn(running):
    page = reader(running["ada"]).get("/").text

    assert not re.search(r"track-presence|track-tools|track__budget|box--overlapping|box__vetoes|box__mark|box__flexible|box--dropped|dropped|Shared|budget", page)
    assert "The Thing" in page


def test_the_menu_has_no_my_warnings_and_there_is_no_nag_bar(running):
    page = reader(running["ada"]).get("/").text

    assert "My warnings" not in page
    assert 'class="nag-bar"' not in page


@pytest.mark.parametrize("what", ["no anchor", "no boxes"])
def test_with_nothing_to_show_the_page_says_the_running_order_is_not_out_yet(running, what):
    if what == "no anchor":
        Timetable.objects.filter(pk=1).update(anchor=None)
    else:
        Box.objects.all().delete()

    page = reader(running["ada"]).get("/").text

    assert "The running order isn&#x27;t out yet." in page or "The running order isn't out yet." in page
    assert "evening__slot" not in page
    assert "data-evening-start" not in page


def test_with_no_timetable_row_at_all_the_page_says_so(voters):
    walk_to(Phase.RUN)

    assert "running order" in reader(voters["ada"]).get("/").text


def test_the_query_count_does_not_grow_with_the_boxes(running):
    client = reader(running["ada"])
    client.get("/")

    def queries():
        with CaptureQueriesContext(connection) as seen:
            client.get("/")
        return len(seen)

    before = queries()
    for index in range(5):
        Box.objects.create(label=f"Break {index}", length=15, start=1000 + index * 20)
        film = Suggestion.objects.suggest(running["voters"]["Hanna"], a_tmdb_film(9000 + index, f"Film {index}", runtime=90), "Pitch.")
        Box.objects.create(suggestion=film, start=2000 + index * 100)

    assert queries() == before


def test_for_an_anchor_in_the_past_the_first_render_marks_past_playing_and_next(running, clock):
    clock.now = datetime(2026, 11, 7, 20, 35, tzinfo=UTC)  # Cube is over, in the gap before The Thing

    page = reader(running["ada"]).get("/").text
    gap = [re.search(r"evening__slot--(\w+)", slot)[1] for slot in slots_of(page)]
    assert gap == ["past", "past", "next", "later"]
    assert "NEXT · in 5m" in page

    clock.now = datetime(2026, 11, 7, 18, 30, tzinfo=UTC)  # a third of the way into Cube
    page = reader(running["ada"]).get("/").text
    assert [re.search(r"evening__slot--(\w+)", slot)[1] for slot in slots_of(page)] == ["playing", "later", "later", "later"]
    assert "NOW PLAYING · 1h left" in page
    assert "--elapsed: 33.333%" in page

    clock.now = datetime(2026, 11, 7, 18, 30, tzinfo=UTC) + timedelta(hours=7)  # Event Horizon is over
    page = reader(running["ada"]).get("/").text
    assert {re.search(r"evening__slot--(\w+)", slot)[1] for slot in slots_of(page)} == {"past"}
    assert "NOW PLAYING" not in page and "NEXT" not in page


def test_for_an_anchor_ahead_the_first_box_is_next_in_two_days(running, clock):
    clock.now = datetime(2026, 11, 5, 18, 0, tzinfo=UTC)

    page = reader(running["ada"]).get("/").text

    assert [re.search(r"evening__slot--(\w+)", slot)[1] for slot in slots_of(page)] == ["next", "later", "later", "later"]
    assert "NEXT · in 2 days" in page


def test_the_page_polls_for_the_evening_every_interval(running, settings):
    settings.POLL_INTERVAL_SECONDS = 20

    region = re.search(r'<section class="evening" id="evening"[^>]*>', reader(running["ada"]).get("/").text)[0]

    assert 'hx-get="/evening/"' in region
    assert 'hx-trigger="every 20s"' in region
    assert 'hx-swap="morph:outerHTML"' in region


def test_the_poll_answers_the_region_alone_with_each_slot_marked(running):
    answer = reader(running["ada"]).get("/evening/", headers={"HX-Request": "true"})

    assert answer.status_code == 200
    assert answer.text.lstrip().startswith('<section class="evening" id="evening"')
    assert "<html" not in answer.text
    assert len(slots_of(answer.text)) == 4
    assert 'data-start="2026-11-07T18:00:00+00:00"' in answer.text


def test_a_box_moved_on_the_track_shows_in_the_next_answer(running):
    client = reader(running["ada"])
    before = client.get("/evening/", headers={"HX-Request": "true"}).text
    Box.objects.filter(label="Dinner").update(start=110)

    after = client.get("/evening/", headers={"HX-Request": "true"}).text

    assert 'data-start="2026-11-07T19:50:00+00:00"' in after
    assert 'data-start="2026-11-07T19:50:00+00:00"' not in before


@pytest.mark.parametrize("phase", [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK])
def test_outside_run_the_poll_reloads_the_tab_into_the_phase(voters, phase):
    walk_to(phase)

    htmx = reader(voters["ada"]).get("/evening/", headers={"HX-Request": "true"})
    plain = reader(voters["ada"]).get("/evening/")

    assert htmx.status_code == 200 and htmx["HX-Redirect"] == "/"
    assert plain.status_code == 302 and plain["Location"] == "/"


def test_the_poll_moving_from_run_to_pick_lands_on_the_reveal(running):
    client = reader(running["ada"])
    move(Phase.RUN, Phase.PICK)

    assert client.get("/evening/", headers={"HX-Request": "true"})["HX-Redirect"] == "/"


def test_the_poll_refuses_a_post(running):
    assert reader(running["ada"]).post("/evening/").status_code == 405


def test_a_plain_get_of_the_poll_in_run_redirects_to_the_page(running):
    answer = reader(running["ada"]).get("/evening/")

    assert answer.status_code == 302 and answer["Location"] == "/"


def test_a_poll_whose_session_has_ended_reloads_the_tab_onto_login(running):
    htmx = Client().get("/evening/", headers={"HX-Request": "true"})
    plain = Client().get("/evening/")

    assert htmx.status_code == 200 and htmx["HX-Redirect"] == "/login/"
    assert plain.status_code == 302 and plain["Location"] == "/login/?next=/evening/"
