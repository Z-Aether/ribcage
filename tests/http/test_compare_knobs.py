"""The first two knobs on Compare: held in the admin's session, scoring every row and re-solving the batch (#17, #66, #167)."""

import re

from ribcage.ballot.models import BallotRecord
from ribcage.identity import admin_session
from ribcage.identity.models import Voter
from tests.http.test_compare_batch import COMPARE, batch, cells, film, many, proposals, text, votes  # noqa: F401

KNOB = "/console/pick/knob/"


def held(admin):
    return admin_session.session_store(admin.cookies[admin_session.COOKIE_NAME].value).get("knobs")


def set_aside(admin, voter, on=True):
    return admin.post(KNOB, {"knob": "without", "voter": voter.pk, "on": "1" if on else "0"})


def disregard(admin, voter, on=True):
    return admin.post(KNOB, {"knob": "disregarded", "voter": voter.pk, "on": "1" if on else "0"})


def line(page):
    found = re.search(r'<p class="floor-line[^"]*"[^>]*data-floor-set>(.*?)</p>', page, re.S)
    return text(found[1]), "floor-line--out" in found[0]


def chips(page, kind):
    return re.findall(rf'<button[^>]*class="([^"]*)"[^>]*data-knob-{kind}>(.*?)</button>', page, re.S)


def points(page):
    return {text(title): int(text(number)) for title, number in re.findall(r'slate-row__title[^>]*>(.*?)</td>.*?slate-row__points">(.*?)</td>', page, re.S)}


def test_with_no_knobs_the_basis_says_so_and_clear_knobs_is_disabled(admin, votes):
    page = admin.get(COMPARE).text

    assert "no knobs · solved in" in text(batch(page))
    assert re.search(r"<button[^>]*disabled[^>]*data-knob-clear", page)
    assert held(admin) is None


def test_without_a_voter_is_held_in_the_session_and_changes_the_rows_and_the_batch(admin, votes):
    ada = votes["voters"]["ada"]
    stored = cells(batch(admin.get(COMPARE).text))

    assert set_aside(admin, ada).status_code == 302
    page = admin.get(COMPARE).text

    assert held(admin) == {"without": [ada.pk], "disregarded": [], "fixed_in": [], "fixed_out": []}
    assert "basis: without ada" in text(batch(page))
    assert cells(batch(page))["sigma"] != stored["sigma"]
    assert line(page)[0] == "Floor computed over 1 of 3 — ada: set aside by knob · Hanna: no ballot"
    assert 'slate-strip__cell--out" title="ada: set aside by knob"' in page
    assert not re.search(r"<button[^>]*disabled[^>]*data-knob-clear", page)
    assert [on for on, _ in [(("is-on" in each), name) for each, name in chips(page, "without")]] == [True, False, False]


def test_the_knob_stays_across_reloads_and_both_sub_tabs_until_cleared(admin, votes):
    set_aside(admin, votes["voters"]["ada"])

    for address in (COMPARE, COMPARE, "/console/pick/compare/"):
        assert "basis: without ada" in text(batch(admin.get(address).text))
    assert held(admin)["without"]

    admin.post(KNOB, {"knob": "clear"})

    assert held(admin) == {"without": [], "disregarded": [], "fixed_in": [], "fixed_out": []}
    assert "no knobs" in text(batch(admin.get(COMPARE).text))


def test_disregarding_a_voters_vetoes_raises_their_vetoed_films_points_and_keeps_the_bar(admin, votes):
    dani = votes["voters"]["Dani"]
    before = admin.get(COMPARE).text
    assert [(name) for _, name in chips(before, "disregard")] == ["Dani (1)"]

    disregard(admin, dani)
    page = admin.get(COMPARE).text

    assert "basis: Dani's vetoes disregarded" in text(batch(page))
    assert chips(page, "disregard")[0][0].count("is-on") == 1
    assert points(page)["Cube"] == points(before)["Cube"] + 2
    assert "Vetoed: Cube (Dani)" in text(page)
    assert line(page)[0] == line(before)[0]


def test_both_knobs_make_one_basis_line(admin, votes):
    set_aside(admin, votes["voters"]["Hanna"])
    disregard(admin, votes["voters"]["Dani"])

    assert "basis: without Hanna · Dani's vetoes disregarded" in text(batch(admin.get(COMPARE).text))


def test_a_knob_change_resets_more(admin, many):
    admin.post("/console/pick/more/")
    assert len(proposals(admin.get(COMPARE).text)) == 6

    set_aside(admin, Voter.objects.get(display_name="ada"))

    assert len(proposals(admin.get(COMPARE).text)) == 3


def test_a_knob_re_solves_the_batch_once_and_the_next_render_resumes(admin, many, monkeypatch):
    from ribcage.timetable import batch as batches

    admin.get(COMPARE)
    solves = []
    real = batches.solve
    monkeypatch.setattr(batches, "solve", lambda *args, **kwargs: solves.append(1) or real(*args, **kwargs))

    admin.get(COMPARE)
    assert solves == []

    set_aside(admin, Voter.objects.get(display_name="ada"))
    page = admin.get(COMPARE).text
    assert len(solves) >= 3 and "nothing new to solve" not in text(batch(page))

    solves.clear()
    assert "nothing new to solve" in text(batch(admin.get(COMPARE).text)) and solves == []


def test_a_removed_voters_knob_falls_out_of_the_basis(admin, votes):
    hanna = votes["voters"]["Hanna"]
    set_aside(admin, hanna)
    disregard(admin, votes["voters"]["Dani"])
    hanna.delete()

    page = admin.get(COMPARE).text

    assert "basis: Dani's vetoes disregarded" in text(batch(page))
    assert held(admin)["without"] == []


def test_a_disregard_knob_whose_vetoes_are_gone_falls_out_too(admin, votes):
    disregard(admin, votes["voters"]["Dani"])
    BallotRecord.objects.filter(vetoed=True).delete()

    assert "no knobs" in text(batch(admin.get(COMPARE).text))
    assert held(admin)["disregarded"] == []


def test_the_rosters_floor_set_ignores_knobs(admin, votes):
    roster = line(admin.get("/console/roster/").text)

    set_aside(admin, votes["voters"]["ada"])

    assert line(admin.get("/console/roster/").text) == roster
    assert "set aside" not in admin.get("/console/roster/").text


def test_a_line_whose_only_outsiders_are_set_aside_by_knob_is_muted_and_otherwise_highlighted(admin, votes):
    BallotRecord.objects.create(voter=votes["voters"]["Hanna"], suggestion=votes["thing"], score=1)
    assert line(admin.get(COMPARE).text) == ("Floor computed over 3 of 3", False)

    set_aside(admin, votes["voters"]["Dani"])
    assert line(admin.get(COMPARE).text) == ("Floor computed over 2 of 3 — Dani: set aside by knob", False)

    BallotRecord.objects.filter(voter=votes["voters"]["Hanna"]).delete()
    assert line(admin.get(COMPARE).text) == ("Floor computed over 1 of 3 — Dani: set aside by knob · Hanna: no ballot", True)


def test_a_voter_outside_the_floor_set_for_another_reason_has_a_dimmed_chip_with_the_reason(admin, votes):
    page = admin.get(COMPARE).text
    dimmed = re.findall(r'<button[^>]*class="[^"]*knob-chip--out[^"]*"[^>]*title="([^"]*)"[^>]*data-knob-without>(.*?)</button>', page)

    assert dimmed == [("no ballot", "Hanna")]


def test_a_stale_or_nonsense_post_changes_nothing(admin, votes):
    for data in ({"knob": "without", "voter": "x", "on": "1"}, {"knob": "nope", "voter": "1"}, {}):
        assert admin.post(KNOB, data).status_code == 302

    assert "no knobs" in text(batch(admin.get(COMPARE).text))


def test_every_knob_form_lands_back_on_compare_so_the_scroll_is_kept(admin, votes):
    set_aside(admin, votes["voters"]["ada"])
    page = admin.get(COMPARE).text
    forms = re.findall(r"<form[^>]*pick/knob/[^>]*>", page)

    assert len(forms) >= 4 and all('data-lands-on="/console/pick/compare/"' in each for each in forms)


def test_a_voter_set_aside_has_no_slate_sum_in_the_breakdown(admin, votes):
    set_aside(admin, votes["voters"]["ada"])
    page = admin.get(COMPARE).text
    row = re.search(r"<tr>\s*<td class=\"slate-row__person\">ada.*?</tr>", page, re.S | re.I)

    assert row and "set aside by knob" in row[0]
    assert text(re.search(r"slate-row__sum[^>]*>(.*?)</td>", row[0], re.S)[1]) == "–"
