"""Presence strips and shared time on the admin's track, and moving with a drag's preview (#12, #22, #139, #149)."""

import re

import pytest

from ribcage.ballot import placing
from ribcage.ballot.placing import VETO
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film

PICK, ANCHOR = "/console/pick/", "/console/pick/anchor/"
PREVIEW = "/console/pick/preview/"


@pytest.fixture
def evening(admin, voters):
    """Cube 0–90, Dinner 100–145, The Thing 160–269, Alien 300–390 from 18:00; Hanna vetoes Cube, ada The Thing, Dani nothing."""
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb_id, title, runtime in [(431, "Cube", 90), (1091, "The Thing", 109), (348, "Alien", 90)]:
        films[title] = Suggestion.objects.suggest(voters["Dani"], a_tmdb_film(tmdb_id, title, runtime=runtime), "A pitch.")
    Suggestion.objects.filter(pk__in=[each.pk for each in films.values()]).update(approval=Approval.APPROVED)
    boxes = {
        "Cube": Box.objects.create(suggestion=films["Cube"], start=0),
        "Dinner": Box.objects.create(label="Dinner", length=45, start=100),
        "The Thing": Box.objects.create(suggestion=films["The Thing"], start=160),
        "Alien": Box.objects.create(suggestion=films["Alien"], start=300),
    }
    placing.place(voters["Hanna"], films["Cube"], VETO)
    placing.place(voters["ada"], films["The Thing"], VETO)
    return {"admin": admin, "voters": voters, "films": films, "boxes": boxes}


def strips_of(page):
    """Each strip's voter name, its bar's left and width, and its holes' titles."""
    found = {}
    for strip in re.findall(r'<li class="track__strip[^"]*".*?</li>', page, re.S):
        name = re.search(r'track__strip-name">([^<]*)<', strip).group(1)
        bar = re.search(r'track__present" style="--at: ([\d.]+)%; --span: ([\d.]+)%', strip)
        found[name] = (bar.groups() if bar else None, re.findall(r'class="track__hole"[^>]*title="([^"]*)"', strip))
    return found


def line_of(page):
    return re.search(r'<p class="track-presence"[^>]*>([^<]*)</p>', page).group(1)


def test_only_the_voters_not_present_throughout_get_a_strip_and_the_line_counts_the_rest(evening):
    page = evening["admin"].get(PICK).text

    strips = strips_of(page)
    assert sorted(strips) == ["Hanna", "ada"]
    assert line_of(page) == "1 of 3 present throughout · shared time 3h11m"
    assert "Shared <strong>3h11m</strong>" in page


def test_a_voters_strip_arrives_after_leading_vetoes_and_a_mid_evening_veto_is_a_hole(evening):
    strips = strips_of(evening["admin"].get(PICK).text)

    hanna_bar, hanna_holes = strips["Hanna"]
    ada_bar, ada_holes = strips["ada"]
    assert hanna_holes == []
    assert ada_holes == ["Vetoed The Thing: steps out"]
    # Hanna misses Cube, so her bar starts after ada's, which starts with the evening.
    assert float(hanna_bar[0]) > float(ada_bar[0])


def test_the_shared_time_is_a_band_behind_the_rows_in_pieces_around_the_holes(evening):
    page = evening["admin"].get(PICK).text

    # 90 to 300 less The Thing's 160 to 269: the band is in two pieces.
    assert page.count('class="track__shared"') == 2


def test_with_nobody_absent_the_strips_and_the_band_go_and_only_the_line_stays(evening):
    placing.place(evening["voters"]["Hanna"], evening["films"]["Cube"], None)
    placing.place(evening["voters"]["ada"], evening["films"]["The Thing"], None)

    page = evening["admin"].get(PICK).text

    assert "track__strips" not in page and 'class="track__shared"' not in page
    assert line_of(page) == "3 of 3 present throughout"


def test_a_dropped_films_vetoes_still_count(evening):
    Suggestion.objects.filter(pk=evening["films"]["The Thing"].pk).update(approval=Approval.DROPPED)

    assert sorted(strips_of(evening["admin"].get(PICK).text)) == ["Hanna", "ada"]


def test_a_voter_who_vetoed_every_film_has_an_empty_strip_and_there_is_no_shared_time(evening):
    for title in ["The Thing", "Alien"]:
        placing.place(evening["voters"]["Hanna"], evening["films"][title], VETO)

    page = evening["admin"].get(PICK).text

    assert strips_of(page)["Hanna"] == (None, [])
    assert "shared time 0m" in line_of(page)


def test_a_drags_preview_answers_with_the_strips_moved(evening):
    before = evening["admin"].get(PICK).text

    # Cube, which Hanna vetoes, goes to the evening's end: she now leaves before it, and ada, with The Thing first, arrives after it.
    response = evening["admin"].post(PREVIEW, {"box": evening["boxes"]["Cube"].pk, "start": "450"})

    page = response.text
    assert "<html" not in page and 'id="track-region"' in page
    assert strips_of(page)["Hanna"][0] != strips_of(before)["Hanna"][0]
    assert line_of(before).endswith("shared time 3h11m") and line_of(page).endswith("shared time 3h01m")
    assert "Shared <strong>3h01m</strong>" in page
    assert Box.objects.get(pk=evening["boxes"]["Cube"].pk).start == 0


def test_the_strips_cost_a_flat_number_of_queries_in_a_preview(evening):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def queries(start):
        with CaptureQueriesContext(connection) as captured:
            evening["admin"].post(PREVIEW, {"box": evening["boxes"]["Cube"].pk, "start": start})
        return len(captured)

    before = queries("450")
    placing.place(evening["voters"]["Dani"], evening["films"]["Alien"], VETO)
    assert queries("450") == before


@pytest.fixture
def candidate(evening):
    """Blade Runner, approved and not on the track; Dani, who is present throughout, vetoes it."""
    film = Suggestion.objects.suggest(evening["voters"]["Dani"], a_tmdb_film(78, "Blade Runner", runtime=100), "A pitch.")
    Suggestion.objects.filter(pk=film.pk).update(approval=Approval.APPROVED)
    placing.place(evening["voters"]["Dani"], film, VETO)
    return film


def test_a_candidates_insert_preview_carries_the_strips_with_the_vetoed_candidate_counted(evening, candidate):
    page = evening["admin"].post(PREVIEW, {"suggestion": candidate.pk, "start": "450", "mode": "none"}).text

    assert 'id="track-region"' in page
    # Dani now leaves before the inserted film at the evening's end.
    assert sorted(strips_of(page)) == ["Dani", "Hanna", "ada"]
    assert line_of(page).startswith("0 of 3 present throughout")


def test_an_arranges_preview_carries_the_strips(evening):
    page = evening["admin"].post(PREVIEW, {"arrange": "spread"}).text

    assert sorted(strips_of(page)) == ["Hanna", "ada"]
    assert "track-presence" in page


def test_arming_an_utility_keeps_the_strips(evening):
    page = evening["admin"].get(f"{PICK}?arrange=lay-out&minutes=10").text

    assert sorted(strips_of(page)) == ["Hanna", "ada"]


def test_a_refusal_over_the_label_keeps_the_typed_length_track_and_its_strips(evening):
    page = evening["admin"].post("/console/pick/box/", {"box": evening["boxes"]["Dinner"].pk, "label": "x" * 200, "length": "60", "mode": "none"}).text

    assert "A label is at most" in page
    assert sorted(strips_of(page)) == ["Hanna", "ada"]
