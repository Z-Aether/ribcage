"""The film knobs on Compare: fix a film in or out, held in the admin's session and changing the batch (#17, #66, #168)."""

import re

from ribcage.ballot.models import BallotRecord
from ribcage.identity import admin_session
from ribcage.suggestions.models import Suggestion
from tests.http.test_compare_batch import COMPARE, batch, cells, many, proposals, text, votes  # noqa: F401
from tests.http.test_compare_knobs import KNOB, held, line


def pin(admin, suggestion, way="fixed_in", on=True):
    return admin.post(KNOB, {"knob": way, "film": suggestion.pk, "on": "1" if on else "0"})


def film_named(title):
    return Suggestion.objects.get(title=title)


def batch_films(page):
    details = [each for each in page.split("data-slate-row>")[1:] if 'class="slate-row__opens"' in each and "Proposal" in each[:400]]
    return [" ".join(text(each) for each in re.findall(r'slate-row__title[^>]*>(.*?)</td>', detail, re.S)) for detail in details]


def dots_of(page, held_by="slate-dot--fixed"):
    return re.findall(rf'<td class="slate-dot[^"]*{held_by}[^"]*">(.*?)</td>', batch(page), re.S)


def options(page, kind):
    found = re.search(rf'<select[^>]*data-knob-select-{kind}[^>]*>(.*?)</select>', page, re.S)[1]
    return [text(each) for each in re.findall(r"<option[^>]*>(.*?)</option>", found, re.S)][1:]


def test_a_film_fixed_in_is_in_the_session_outlined_in_every_proposal_and_named_on_the_basis_line(admin, many):
    pinned = film_named("Film 5")

    assert pin(admin, pinned).status_code == 302
    page = admin.get(COMPARE).text

    assert held(admin)["fixed_in"] == [pinned.pk] and held(admin)["fixed_out"] == []
    assert len(proposals(page)) == 3
    assert len(batch_films(page)) == 3 and all("Film 5" in each for each in batch_films(page))
    assert "basis: Film 5 fixed in" in text(batch(page))
    rows = [each for each in page.split("data-slate-row>")[1:] if "Proposal" in each[:400]]
    assert len(rows) == 3 and all('slate-dot--fixed"><span class="slate-dot__mark"' in each.split("</tr>")[0] for each in rows)


def test_a_film_fixed_out_is_in_no_proposal_and_the_batch_changes(admin, many):
    before = batch_films(admin.get(COMPARE).text)
    top = film_named(re.findall(r"Film \d", before[0])[0])

    pin(admin, top, "fixed_out")
    page = admin.get(COMPARE).text

    assert held(admin)["fixed_out"] == [top.pk]
    assert before[0] and top.title not in " ".join(batch_films(page)) and batch_films(page) != before
    assert f"{top.title} fixed out" in text(batch(page))


def test_each_film_knob_resets_more_and_clear_knobs_clears_both(admin, many):
    admin.post("/console/pick/more/")
    assert len(proposals(admin.get(COMPARE).text)) == 6

    pin(admin, film_named("Film 1"))
    assert len(proposals(admin.get(COMPARE).text)) == 3
    pin(admin, film_named("Film 2"), "fixed_out")
    assert "Film 1 fixed in · Film 2 fixed out" in text(batch(admin.get(COMPARE).text))

    admin.post(KNOB, {"knob": "clear"})

    assert held(admin) == {"without": [], "disregarded": [], "fixed_in": [], "fixed_out": []}
    assert "no knobs" in text(batch(admin.get(COMPARE).text))


def test_a_film_is_fixed_in_or_out_never_both(admin, many):
    one = film_named("Film 3")
    pin(admin, one)
    pin(admin, one, "fixed_out")

    assert (held(admin)["fixed_in"], held(admin)["fixed_out"]) == ([], [one.pk])
    pin(admin, one)
    assert (held(admin)["fixed_in"], held(admin)["fixed_out"]) == ([one.pk], [])


def test_the_selects_leave_out_the_films_already_fixed_either_way_and_each_fixed_film_has_a_chip(admin, many):
    everything = options(admin.get(COMPARE).text, "in")
    pin(admin, film_named("Film 0"))
    pin(admin, film_named("Film 4"), "fixed_out")
    page = admin.get(COMPARE).text

    assert len(everything) == 6 and all(each.endswith("(100m)") for each in everything)
    assert sorted(options(page, "in")) == sorted(options(page, "out")) and len(options(page, "in")) == 4
    assert not any(title in " ".join(options(page, "in")) for title in ("Film 0", "Film 4"))
    assert re.search(r'<button[^>]*data-knob-fixed-in>\s*Film 0 \(100m\)', page)
    assert re.search(r'<button[^>]*data-knob-fixed-out>\s*Film 4 \(100m\)', page)


def test_a_film_dropped_since_falls_out_of_the_basis(admin, many):
    gone = film_named("Film 2")
    pin(admin, gone)
    pin(admin, film_named("Film 3"), "fixed_out")
    gone.approval = "dropped"
    gone.save()

    page = admin.get(COMPARE).text

    assert "Film 2" not in text(batch(page)).split("solved in")[0]
    assert held(admin)["fixed_in"] == [] and held(admin)["fixed_out"] != []


def test_pins_beyond_the_budget_give_no_proposal_and_the_banner_names_them(admin, many):
    pin(admin, film_named("Film 1"))
    pin(admin, film_named("Film 2"))
    pin(admin, film_named("Film 3"))
    page = admin.get(COMPARE).text

    assert proposals(page) == []
    banner = text(re.search(r'data-batch-banner>(.*?)</div>\s*</', batch(page), re.S)[1])
    assert re.search(r"The films fixed in alone exceed the budget: (Film \d \(100m\)(, )?){3}\. Nothing dropped\.", banner)
    assert re.search(r"<button[^>]*disabled[^>]*data-batch-more", page)
    assert "No slate holds the films fixed in." in text(re.search(r'id="batch-more-reason"[^>]*>(.*?)</span>', page, re.S)[1])


def test_every_candidate_fixed_out_says_so_rather_than_that_no_film_is_approved(admin, many):
    for number in range(6):
        pin(admin, film_named(f"Film {number}"), "fixed_out")
    page = admin.get(COMPARE).text

    assert "Every film is fixed out, so there is nothing to propose." in text(batch(page))
    assert "No film is approved" not in text(batch(page))


def test_the_floor_set_takes_a_film_fixed_out_so_its_only_fan_is_nothing_representable(admin, many):
    BallotRecord.objects.filter(voter__display_name="Dani").exclude(suggestion__title="Film 1").update(score=0)
    assert "Dani: nothing representable" not in line(admin.get(COMPARE).text)[0]

    pin(admin, film_named("Film 1"), "fixed_out")

    assert "Dani: nothing representable" in line(admin.get(COMPARE).text)[0]


def test_a_nonsense_film_post_changes_nothing(admin, many):
    admin.post(KNOB, {"knob": "fixed_in", "film": "x", "on": "1"})
    admin.post(KNOB, {"knob": "fixed_in", "on": "1"})

    assert held(admin)["fixed_in"] == []


def test_a_film_that_is_no_candidate_is_dropped_from_a_posted_basis_on_the_next_render(admin, many):
    admin.post(KNOB, {"knob": "fixed_in", "film": "99999", "on": "1"})
    admin.get(COMPARE)

    assert held(admin)["fixed_in"] == []


def test_every_film_knob_form_lands_back_on_compare_so_the_scroll_is_kept(admin, many):
    page = admin.get(COMPARE).text
    forms = re.findall(r'<form[^>]*action="/console/pick/knob/"[^>]*>', page)

    assert len(forms) >= 6 and all('data-lands-on="/console/pick/compare/"' in each for each in forms)
