"""*Use this slate* on the Timetable tab: the shortlist beside the track, armed by a GET, applied by a POST (#12, #36, #171)."""

import re

import pytest

from ribcage.ballot.models import BallotRecord
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.shortlist import keeping
from ribcage.shortlist.models import KeptProposal
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.timetable.models import Box
from tests.films import a_tmdb_film
from tests.http.test_phase import walk_to

PICK, ANCHOR, USE, PREVIEW = "/console/pick/", "/console/pick/anchor/", "/console/pick/use/", "/console/pick/preview/"


@pytest.fixture
def shortlisted(admin, voters):
    """Cube 90, The Thing 109, Alien 117 and Dune 155, all approved; Dune is dropped since. Cube is on the timetable with a Break.

    Votes put the slate order at Alien (3 points), The Thing (2), Dune (0, a veto-free tie broken by title after Cube), Cube vetoed.
    """
    walk_to(Phase.PICK)
    admin.post(ANCHOR, {"anchor": "2026-11-07T18:00"})
    films = {}
    for tmdb, title, runtime in ((431, "Cube", 90), (1091, "The Thing", 109), (348, "Alien", 117), (438631, "Dune", 155)):
        films[title] = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(tmdb, title, runtime=runtime), "Why.")
    Suggestion.objects.filter(pk__in=[each.pk for each in films.values()]).update(approval=Approval.APPROVED)
    hanna = voters["Hanna"]
    BallotRecord.objects.create(voter=hanna, suggestion=films["Alien"], score=3)
    BallotRecord.objects.create(voter=hanna, suggestion=films["The Thing"], score=2)
    BallotRecord.objects.create(voter=voters["ada"], suggestion=films["Cube"], vetoed=True)
    proposal = keeping.keep([each.pk for each in films.values()], "found under: no knobs")
    Suggestion.objects.filter(pk=films["Dune"].pk).update(approval=Approval.DROPPED)
    Box.objects.create(suggestion=films["Cube"], start=40)
    Box.objects.create(label="Break", length=30, start=200)
    return {"admin": admin, "films": films, "proposal": proposal, "voters": voters}


def laid(page):
    return [(int(start), int(length)) for start, length in re.findall(r'class="track__slot[^"]*"[^>]*data-start="(-?\d+)" data-length="(\d+)"', page)]


def stored():
    return [(each.suggestion.title if each.suggestion else each.label, each.start) for each in Box.objects.select_related("suggestion").order_by("start")]


def test_arming_writes_nothing_and_shows_the_laid_track_armed_and_inert(shortlisted):
    before = stored()

    page = shortlisted["admin"].get(f"{PICK}?use={shortlisted['proposal'].pk}").text

    assert stored() == before
    assert sorted(laid(page)) == [(0, 117), (117, 109), (226, 155), (381, 90)]
    assert "data-armed" in page
    assert "Use Kept 1: 4 films, ends Sun 01:51" in page
    assert f'action="{USE}"' in page and ">Apply</button>" in page and re.search(r'<a class="button button--quiet arrange__cancel" href="/console/pick/">Cancel</a>', page)
    assert "track__handle" not in page and "Spread evenly" not in page and "Lay out" not in page
    assert "ripple-mode" not in page and "+ Break" not in page


def test_apply_replaces_every_box_breaks_included_in_slate_order(shortlisted):
    response = shortlisted["admin"].post(USE, {"use": shortlisted["proposal"].pk})

    assert response.status_code in (200, 302)
    assert stored() == [("Alien", 0), ("The Thing", 117), ("Dune", 226), ("Cube", 381)]
    assert not Box.objects.filter(suggestion__isnull=True).exists()


def test_the_preview_and_the_save_lay_the_same_films(shortlisted):
    page = shortlisted["admin"].get(f"{PICK}?use={shortlisted['proposal'].pk}").text
    shown = [int(each) for each in re.findall(r'class="track__slot[^"]*"[^>]*data-start="(-?\d+)"', page)]

    shortlisted["admin"].post(USE, {"use": shortlisted["proposal"].pk})

    assert shown == sorted(start for _, start in stored())


def test_the_preview_route_answers_the_laid_track_as_a_fragment(shortlisted):
    before = stored()

    page = shortlisted["admin"].post(PREVIEW, {"use": shortlisted["proposal"].pk}).text

    assert stored() == before
    assert "data-armed" in page and "Use Kept 1" in page and "<html" not in page


def test_a_kept_dropped_film_is_laid_with_its_mark(shortlisted):
    armed = shortlisted["admin"].get(f"{PICK}?use={shortlisted['proposal'].pk}").text
    shortlisted["admin"].post(USE, {"use": shortlisted["proposal"].pk})
    saved = shortlisted["admin"].get(PICK).text

    assert armed.count("box__mark") == saved.count("box__mark") == 1
    assert Box.objects.filter(suggestion__title="Dune").exists()


def test_a_discarded_kept_proposal_writes_nothing(shortlisted):
    pk = shortlisted["proposal"].pk
    keeping.discard(pk)
    before = stored()

    armed = shortlisted["admin"].get(f"{PICK}?use={pk}").text
    shortlisted["admin"].post(USE, {"use": pk})
    shortlisted["admin"].post(USE, {"use": "nonsense"})

    assert "data-armed" not in armed
    assert stored() == before


def test_without_an_anchor_use_this_slate_is_disabled_with_the_line(shortlisted):
    from ribcage.timetable.models import Timetable

    Timetable.objects.update(anchor=None)

    page = shortlisted["admin"].get(PICK).text

    assert re.search(r"<button[^>]*data-use disabled", page)
    assert "Set the start time above first." in page.split('class="shortlist"')[1]
    assert "data-armed" not in shortlisted["admin"].get(f"{PICK}?use={shortlisted['proposal'].pk}").text


def test_the_shortlist_half_shows_the_compact_rows_in_the_order_kept(shortlisted):
    keeping.keep([shortlisted["films"]["Cube"].pk], "found under: no knobs")

    half = shortlisted["admin"].get(PICK).text.split('class="shortlist"')[1]

    assert half.count("slate-row--compact") == 2
    assert half.index("Kept 1") < half.index("Kept 2")
    assert "tier" in half and "slate-strip" in half and "dropped: Dune" in half
    assert "slate-dot" not in half and "data-slate-row>" not in half


def test_with_nothing_kept_the_half_reads_one_muted_line(shortlisted):
    KeptProposal.objects.all().delete()

    half = shortlisted["admin"].get(PICK).text.split('class="shortlist"')[1]

    assert "Nothing kept yet." in half and "slate-row--compact" not in half


def test_it_works_in_run_and_over_an_empty_timetable(shortlisted):
    Box.objects.all().delete()
    move(Phase.PICK, Phase.RUN)

    page = shortlisted["admin"].get(f"{PICK}?use={shortlisted['proposal'].pk}").text
    shortlisted["admin"].post(USE, {"use": shortlisted["proposal"].pk})

    assert "data-armed" in page
    assert [name for name, _ in stored()] == ["Alien", "The Thing", "Dune", "Cube"]


def test_the_shortlist_row_keeps_its_label_a_table_cell_and_the_table_sits_in_a_scroll_frame(shortlisted):
    page = shortlisted["admin"].get(PICK).text

    assert re.search(r'<td class="slate-row__label"><div class="slate-row__labelled">', page)
    assert re.search(r'<div class="slate-ledger__frame">\s*<table class="ledger slate-ledger slate-ledger--compact"', page)


def test_the_split_columns_may_shrink_and_the_gallery_hides_no_cell_of_the_compact_row():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "ribcage" / "static"
    theme = (root / "theme" / "theme.css").read_text(encoding="utf8")
    gallery = (root / "gallery" / "gallery.css").read_text(encoding="utf8")

    assert theme.count("grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);") >= 1
    assert ".slate-row--compact .slate-row__label {\n  display: flex" not in theme
    assert ".ledger td:nth-child(4)" not in gallery.replace(".ledger:not(.slate-ledger--compact) td:nth-child(4)", "")


@pytest.mark.django_db
def test_the_previewed_boxes_are_the_boxes_the_save_stores(shortlisted):
    from dataclasses import replace

    from ribcage.timetable import track, using

    films = [each.pk for each in shortlisted["films"].values()]
    previewed = using.lay(films, save=False)
    saved = using.lay(films, save=True)

    assert [replace(each, key=0) for each in previewed] == [replace(each, key=0) for each in saved]
