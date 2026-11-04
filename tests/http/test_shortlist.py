"""The shortlist on Compare: keep a batch proposal, rescored live under the basis, discard it, and its hold on its films (#17, #26 §5, #66, #169)."""

import re

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.test.utils import CaptureQueriesContext

from ribcage.identity.removal import remove
from ribcage.phase.history import move
from ribcage.phase.order import Phase
from ribcage.shortlist import keeping
from ribcage.shortlist.models import KeptFilm, KeptProposal
from ribcage.suggestions.models import Approval, Suggestion
from tests.films import a_tmdb_film
from tests.http.test_compare_batch import COMPARE, batch, cells, many, proposals, text, votes  # noqa: F401
from tests.http.test_compare_knobs import KNOB, set_aside
from tests.http.test_phase import walk_to
from tests.http.test_runtime_pencil import pencils_on
from tests.http.test_withdraw import arms_on

KEEP = "/console/pick/keep/"
DISCARD = "/console/pick/discard/"
HTMX = {"HX-Request": "true"}


def section(page, name):
    # A row's detail tables hold tbody of their own, so the section runs to the next section's start.
    return re.search(rf'aria-label="{name}">(.*?)(?=<tbody class="slate-ledger__section"|</table>\s*</div>\s*</section>)', page, re.S)[1]


def shortlist(page):
    return section(page, "Shortlist")


def kept_rows(page):
    return re.findall(r'<tr class="slate-row" data-slate-row>.*?</tr>', shortlist(page), re.S)


def sets_offered(page):
    """The film set of each batch row that offers keep."""
    return re.findall(r'name="films" value="([\d,]*)"><button[^>]*data-keep>', section(page, "This batch"))


def keep_first(admin):
    offered = sets_offered(admin.get(COMPARE).text)[0]
    return admin.post(KEEP, {"films": offered}), offered


def provenance_of(page):
    return [text(each) for each in re.findall(r'<span class="slate-row__provenance" data-provenance>(.*?)</span>', shortlist(page), re.S)]


def points_of(page, title):
    detail = shortlist(page).split('class="ledger__detail')[1]
    return int(re.search(rf"{title}.*?slate-row__points\">(\d+)", detail, re.S)[1])


def test_keep_stores_the_film_set_and_a_plain_copy_of_the_basis_and_reloads_compare(admin, many, voters):
    set_aside(admin, voters["Dani"])
    offered = sets_offered(admin.get(COMPARE).text)[0]

    reply = admin.post(KEEP, {"films": offered})

    assert reply.status_code == 302 and reply["Location"] == COMPARE
    proposal = KeptProposal.objects.get()
    assert proposal.provenance == "without Dani"
    assert sorted(KeptFilm.objects.filter(proposal=proposal).values_list("suggestion_id", flat=True)) == sorted(int(each) for each in offered.split(","))


def test_a_kept_row_is_rescored_under_the_basis_and_its_provenance_says_so(admin, many, voters):
    keep_first(admin)
    before = admin.get(COMPARE).text
    assert provenance_of(before) == ["found under the current basis: no knobs"]
    stored = cells(shortlist(before))

    set_aside(admin, voters["ada"])
    after = admin.get(COMPARE).text

    assert provenance_of(after) == ["found under: no knobs · rescored under the current basis"]
    assert cells(shortlist(after))["sigma"] != stored["sigma"]
    assert "found under: no knobs · rescored under the current basis" in text(shortlist(after).split('class="ledger__detail')[1])

    admin.post(KNOB, {"knob": "clear"})
    assert provenance_of(admin.get(COMPARE).text) == ["found under the current basis: no knobs"]


def test_a_proposal_found_under_a_knob_reads_current_while_that_knob_is_on(admin, many, voters):
    set_aside(admin, voters["ada"])
    keep_first(admin)

    assert provenance_of(admin.get(COMPARE).text) == ["found under the current basis: without ada"]


def test_a_film_knob_is_named_by_its_title_in_the_provenance(admin, many):
    pinned = Suggestion.objects.get(title="Film 5")
    admin.post(KNOB, {"knob": "fixed_in", "film": pinned.pk, "on": "1"})

    keep_first(admin)

    assert KeptProposal.objects.get().provenance == "Film 5 fixed in"
    assert provenance_of(admin.get(COMPARE).text) == ["found under the current basis: Film 5 fixed in"]


def test_a_batch_proposal_already_kept_reads_kept_and_offers_no_keep(admin, many):
    _, offered = keep_first(admin)
    page = admin.get(COMPARE).text
    rows = re.findall(r'<tr class="slate-row" data-slate-row>.*?</tr>', section(page, "This batch"), re.S)

    assert "data-kept" in rows[0] and "data-keep>" not in rows[0]
    assert all("data-keep>" in each for each in rows[1:])
    assert offered not in sets_offered(page)
    assert admin.post(KEEP, {"films": offered}).status_code == 302
    assert KeptProposal.objects.count() == 1


def test_the_shortlist_sits_between_the_plan_and_the_batch_in_the_order_kept(admin, many):
    assert "Nothing kept yet." in text(shortlist(admin.get(COMPARE).text))
    first, second = sets_offered(admin.get(COMPARE).text)[:2]
    admin.post(KEEP, {"films": second})
    admin.post(KEEP, {"films": first})
    page = admin.get(COMPARE).text

    assert re.findall(r'<tbody class="slate-ledger__section" aria-label="([^"]*)"', page) == ["The plan", "Shortlist", "This batch"]
    assert re.findall(r'class="slate-row__opens"[^>]*>\s*(Kept \d+)', page) == ["Kept 1", "Kept 2"]
    assert [list(each.films) for each in keeping.load()] == [sorted(int(pk) for pk in second.split(",")), sorted(int(pk) for pk in first.split(","))]


def test_discard_takes_the_proposal_off_at_once(admin, many):
    _, offered = keep_first(admin)
    proposal = KeptProposal.objects.get()

    reply = admin.post(DISCARD, {"proposal": proposal.pk})

    assert reply.status_code == 302 and reply["Location"] == COMPARE
    assert not KeptProposal.objects.exists() and not KeptFilm.objects.exists()
    assert offered in sets_offered(admin.get(COMPARE).text)
    assert admin.post(DISCARD, {"proposal": proposal.pk}).status_code == 302
    assert admin.post(DISCARD, {"proposal": "x"}).status_code == 302


def test_a_keep_naming_a_dropped_film_writes_nothing_and_reloads(admin, many):
    offered = sets_offered(admin.get(COMPARE).text)[0]
    Suggestion.objects.filter(pk=int(offered.split(",")[0])).update(approval=Approval.DROPPED)

    reply = admin.post(KEEP, {"films": offered})

    assert reply.status_code == 302 and reply["Location"] == COMPARE
    assert not KeptProposal.objects.exists()


@pytest.mark.parametrize("films", ["", ",", "x", "99999"])
def test_a_keep_naming_no_film_or_a_stranger_writes_nothing(admin, many, films):
    assert admin.post(KEEP, {"films": films}).status_code == 302
    assert not KeptProposal.objects.exists()


def test_a_kept_film_dropped_since_shows_dropped_and_keeps_counting(admin, many):
    _, offered = keep_first(admin)
    before = admin.get(COMPARE).text
    gone = next(each for each in Suggestion.objects.filter(pk__in=offered.split(",")).order_by("title") if each.title != "Film 0")
    counted = points_of(before, gone.title)
    assert counted > 0

    Suggestion.objects.filter(pk=gone.pk).update(approval=Approval.DROPPED)
    page = admin.get(COMPARE).text
    row = kept_rows(page)[0]

    assert re.search(rf"data-dropped[^>]*>\s*dropped: {gone.title}\s*</span>", row)
    assert points_of(page, gone.title) == counted
    assert "slate-row__dropped" in shortlist(page).split('class="ledger__detail')[1]
    assert cells(shortlist(page))["films"].startswith(cells(shortlist(before))["films"])
    assert KeptFilm.objects.filter(suggestion=gone).exists()


def test_removing_a_voter_named_in_provenance_leaves_the_kept_proposal_readable(admin, many, voters):
    set_aside(admin, voters["Dani"])
    keep_first(admin)

    remove(voters["Dani"])
    page = admin.get(COMPARE).text

    assert KeptProposal.objects.get().provenance == "without Dani"
    assert provenance_of(page) == ["found under: without Dani · rescored under the current basis"]
    assert len(kept_rows(page)) == 1


def test_the_query_count_does_not_grow_with_the_shortlist(admin, many):
    def queries():
        with CaptureQueriesContext(connection) as captured:
            admin.get(COMPARE)
        return len(captured)

    admin.get(COMPARE)
    films = list(Suggestion.objects.order_by("pk").values_list("pk", flat=True))
    keeping.keep(films[:2], "no knobs")
    small = queries()
    for start in range(1, 5):
        keeping.keep(films[start : start + 3], "no knobs")

    assert KeptProposal.objects.count() == 5
    assert queries() == small


@pytest.fixture
def held(voters):
    """Hanna's film, approved and kept, then dropped, and a free one beside it, with the group back in SUGGEST."""
    kept = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(1091, "The Thing", runtime=109), "Lights off.")
    free = Suggestion.objects.suggest(voters["Hanna"], a_tmdb_film(431, "Cube", runtime=90), "Six strangers.")
    Suggestion.objects.filter(pk=kept.pk).update(approval=Approval.APPROVED)
    assert keeping.keep([kept.pk], "no knobs")
    Suggestion.objects.filter(pk=kept.pk).update(approval=Approval.DROPPED)
    walk_to(Phase.VOTE)
    move(Phase.VOTE, Phase.APPROVE)
    move(Phase.APPROVE, Phase.SUGGEST)
    return kept, free


def test_a_dropped_film_on_a_kept_proposal_offers_neither_withdraw_nor_the_pencil(client, voters, held):
    _, free = held
    client.force_login(voters["Hanna"])

    page = client.get("/").text

    assert arms_on(page) == [free.pk]
    assert pencils_on(page) == [free.pk]


def test_a_stale_withdraw_or_pencil_on_it_is_refused_and_changes_nothing(client, voters, held):
    kept, _ = held
    client.force_login(voters["Hanna"])

    client.post("/withdraw/", {"suggestion": kept.pk}, headers=HTMX)
    client.post("/runtime/", {"suggestion": kept.pk, "runtime": "127"}, headers=HTMX)

    assert Suggestion.objects.filter(pk=kept.pk, runtime=109, tmdb_runtime=109).exists()


def test_deleting_a_kept_film_directly_fails_on_protect(held):
    kept, _ = held

    with pytest.raises(ProtectedError):
        Suggestion.objects.get(pk=kept.pk).delete()
