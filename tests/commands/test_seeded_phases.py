from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.db.models import F
from django.test import override_settings
from django.utils import timezone

from ribcage.ballot.floor import of_the_roster
from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.films.corpus import read_entries
from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Approval, Note, Suggestion
from ribcage.timetable import engine
from ribcage.timetable.engine import Placed
from ribcage.timetable.models import Box, Timetable
from ribcage.timetable.plan import load as plan_load
from tests.commands.test_seed import CABINET_OF_CURIOSITIES, SEEDED_DISPLAY_NAMES, SEEDED_PASSWORD

# Tests here only read a seeded database, so each phase is seeded once for the module and each test rolls back.
# In a module of its own, since test_seed.py's transactional tests would flush the seed and see it.
pytestmark = pytest.mark.usefixtures("fast_hashing")
FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(scope="module")
def seeded(request, django_db_setup, django_db_blocker):
    with django_db_blocker.unblock(), override_settings(DEBUG=True, PASSWORD_HASHERS=FAST_HASHERS):
        call_command("seed", "--phase", request.param, stdout=StringIO())
    yield request.param
    with django_db_blocker.unblock():
        call_command("flush", interactive=False, verbosity=0)


def pitch_of(suggestion):
    return suggestion.notes.filter(author=suggestion.suggester).first()


@pytest.mark.parametrize("seeded", [Phase.SUGGEST], indirect=True)
@pytest.mark.parametrize("display_name", SEEDED_DISPLAY_NAMES)
def test_every_seeded_voter_signs_in_with_the_known_password(db, seeded, display_name):
    voter = authenticate(display_name=display_name, password=SEEDED_PASSWORD)

    assert voter is not None
    assert voter.display_name == display_name


@pytest.mark.parametrize("seeded", PHASES, indirect=True)
def test_each_phase_lands_there_by_a_walk_one_step_at_a_time(db, seeded):
    walk = list(PhaseMove.objects.order_by("pk"))
    assert current() is seeded
    assert [move.phase for move in walk] == PHASES[1 : PHASES.index(seeded) + 1]
    assert [move.at for move in walk] == sorted(move.at for move in walk)
    assert all(move.at < timezone.now() for move in walk)
    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is not None


@pytest.mark.parametrize("seeded", PHASES, indirect=True)
def test_each_phase_is_seeded_with_a_pool_from_the_recorded_corpus(db, seeded):
    pool = list(Suggestion.objects.select_related("suggester"))
    corpus_ids = {entry.tmdb_id for entry in read_entries()}
    assert len(pool) >= 10
    assert {suggestion.tmdb_id for suggestion in pool} <= corpus_ids
    assert all(suggestion.suggester.display_name == suggestion.suggester_name for suggestion in pool)
    assert len({suggestion.suggester_name for suggestion in pool}) >= 4
    assert all(pitch_of(suggestion) is not None for suggestion in pool)
    assert Note.objects.exclude(author=F("suggestion__suggester")).exists()


@pytest.mark.parametrize("seeded", PHASES, indirect=True)
def test_each_phase_is_seeded_with_the_corpus_hand_entered_film(db, seeded):
    cabinet = Suggestion.objects.get(title=CABINET_OF_CURIOSITIES)
    assert (cabinet.tmdb_id, cabinet.runtime, cabinet.tmdb_runtime, cabinet.poster_path) == (None, 47, None, None)


@pytest.mark.parametrize("seeded", PHASES[1:], indirect=True)
def test_from_approve_on_the_pool_is_a_mix_of_undecided_approved_and_dropped(db, seeded):
    assert set(Suggestion.objects.values_list("approval", flat=True)) == set(Approval)


@pytest.mark.parametrize("seeded", PHASES[: PHASES.index(Phase.VOTE)], indirect=True)
def test_before_vote_nobody_has_a_score_or_is_done(db, seeded):
    assert not BallotRecord.objects.filter(score__isnull=False).exists() and not DoneMarker.objects.exists()


@pytest.mark.parametrize("seeded", PHASES[: PHASES.index(Phase.VOTE)], indirect=True)
def test_before_vote_several_voters_have_vetoed_and_seen_undecided_films_with_and_without_notes(db, seeded):
    vetoes = BallotRecord.objects.filter(vetoed=True)
    noted = [veto for veto in vetoes if Note.objects.filter(suggestion=veto.suggestion, author=veto.voter).exists()]

    assert vetoes.values("voter").distinct().count() >= 3 and BallotRecord.objects.filter(seen_it=True).values("voter").distinct().count() >= 3
    assert vetoes.filter(suggestion__approval=Approval.UNDECIDED).exists() and 0 < len(noted) < vetoes.count()
    assert BallotRecord.objects.filter(seen_it=True, vetoed=True).exists()


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_a_film_vetoed_before_its_approval_is_in_the_veto_band_and_one_only_seen_has_no_say(db, seeded):
    early = BallotRecord.objects.get(voter__display_name="Anne-Marie", suggestion__title="Goodnight Mommy")
    seen_only = BallotRecord.objects.get(voter__display_name="Sam", suggestion__title="Infested")

    assert early.vetoed and early.score is None and early.suggestion.approval == Approval.APPROVED
    assert seen_only.seen_it and not seen_only.vetoed and seen_only.score is None


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_anne_marie_and_obrien_are_done_and_bartholomew_is_not(db, seeded):
    assert set(DoneMarker.objects.values_list("voter__display_name", flat=True)) == {"Anne-Marie", "O'Brien"}


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_ada_has_scored_most_of_the_ballot_zoe_part_and_bartholomew_none(db, seeded):
    ballot = Suggestion.objects.filter(approval=Approval.APPROVED).count()

    def scored(name):
        return BallotRecord.objects.filter(voter__display_name=name, suggestion__approval=Approval.APPROVED).count()

    assert ballot > 8
    assert ballot / 2 < scored("Ada") < ballot
    assert 0 < scored("Zoë") < scored("Ada")
    assert scored("Bartholomew Winthrop") == 0
    assert not BallotRecord.objects.exclude(suggestion__approval=Approval.APPROVED).exists()
    assert set(BallotRecord.objects.filter(vetoed=False, score__isnull=False).values_list("score", flat=True)) == {-1, 0, 1, 2, 3}


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_vetoes_have_a_note_written_for_it_or_in_suggest_or_none_and_one_film_is_vetoed_by_two(db, seeded):
    vetoes = BallotRecord.objects.filter(vetoed=True)
    with_note = [veto for veto in vetoes if Note.objects.filter(suggestion=veto.suggestion, author=veto.voter).exists()]

    # Zoë wrote hers as the reason, Anne-Marie's Terrifier is her SUGGEST note, and Sam has none (#128); Anne-Marie's early Goodnight Mommy came with a note (#152).
    assert sorted(veto.voter.display_name for veto in with_note) == ["Anne-Marie", "Anne-Marie", "Zoë"]
    assert len(with_note) == vetoes.count() - 1
    assert vetoes.filter(score__isnull=False).count() == 0
    assert max(vetoes.filter(suggestion=suggestion).count() for suggestion in Suggestion.objects.filter(ballot_records__vetoed=True)) == 2


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_some_films_are_seen_one_seen_and_scored_and_one_seen_and_vetoed(db, seeded):
    seen = BallotRecord.objects.filter(seen_it=True)

    assert seen.count() >= 3
    assert seen.filter(score__isnull=False).exists() and seen.filter(vetoed=True).exists()


@pytest.mark.parametrize("seeded", PHASES[: PHASES.index(Phase.PICK)], indirect=True)
def test_before_pick_the_anchor_and_the_budget_are_empty(db, seeded):
    assert not Timetable.objects.exists()


@pytest.mark.parametrize("seeded", [Phase.PICK, Phase.RUN], indirect=True)
def test_in_pick_and_run_the_anchor_is_a_saturday_at_18_in_the_time_zone_at_least_two_days_out_and_the_budget_is_9_h(db, seeded):
    timetable = Timetable.objects.get()
    anchor = timezone.localtime(timetable.anchor)

    assert (anchor.weekday(), anchor.hour, anchor.minute) == (5, 18, 0)
    assert anchor - timezone.now() >= timedelta(days=1, hours=18)
    assert timetable.budget == 540


@pytest.mark.parametrize("seeded", [Phase.PICK, Phase.RUN], indirect=True)
def test_in_pick_and_run_the_evening_is_hand_built_within_the_budget_with_no_overlap(db, seeded):
    boxes = list(Box.objects.select_related("suggestion").order_by("start"))
    films = [box for box in boxes if box.suggestion]
    reading = engine.read([Placed(box.pk, box.start, box.suggestion.runtime if box.suggestion else box.length, bool(box.suggestion)) for box in boxes], 540)

    assert 5 <= len(films) <= 6
    assert [box.length for box in boxes if not box.suggestion] == [45] and boxes[0].suggestion and boxes[-1].suggestion
    assert reading.overlaps == () and reading.over < 0
    gaps = [after.start - (before.start + (before.suggestion.runtime if before.suggestion else before.length)) for before, after in zip(boxes, boxes[1:])]
    assert all(10 <= gap <= 20 for gap in gaps)
    assert Box.objects.filter(label="Dinner").get().start > boxes[0].start
    assert Suggestion.objects.filter(approval=Approval.APPROVED, box__isnull=True).count() >= 4


@pytest.mark.parametrize("seeded", [Phase.PICK, Phase.RUN], indirect=True)
def test_in_pick_and_run_terrifier_is_last_vetoed_by_zoe_and_anne_marie_and_sam_vetoes_a_mid_evening_film(db, seeded):
    boxes = list(Box.objects.select_related("suggestion").order_by("start"))
    vetoers = lambda box: sorted(BallotRecord.objects.filter(suggestion=box.suggestion, vetoed=True).values_list("voter__display_name", flat=True))

    assert boxes[-1].suggestion.title == "Terrifier" and vetoers(boxes[-1]) == ["Anne-Marie", "Zoë"]
    middle = boxes[len(boxes) // 2 - 1 : len(boxes) // 2 + 2]
    assert any(box.suggestion and vetoers(box) == ["Sam"] for box in middle)


@pytest.mark.parametrize("seeded", [Phase.PICK, Phase.RUN], indirect=True)
def test_in_pick_and_run_the_seeded_evening_shows_sams_strip_with_a_hole_and_zoe_and_anne_marie_leaving_before_terrifier(db, seeded):
    from ribcage.timetable import track

    timetable = Timetable.objects.get()
    built = track.load(timetable.anchor, timetable.budget)
    boxes = list(Box.objects.select_related("suggestion").order_by("start"))
    terrifier = boxes[-1]
    when_evil_lurks = next(box for box in boxes if box.suggestion and box.suggestion.title == "When Evil Lurks")

    strips = {strip.name: strip for strip in built.strips}
    assert sorted(strips) == ["Anne-Marie", "Sam", "Zoë"]
    assert len(strips["Sam"].holes) == 1 and not strips["Sam"].empty
    assert strips["Zoë"].holes == () and strips["Anne-Marie"].holes == ()
    assert built.presence_line.startswith("3 of 6 present throughout · shared time ")
    first = boxes[0].start
    # Everyone is there from the evening's start until Terrifier, less the one film Sam steps out for.
    assert built.tools.shared == track.duration(terrifier.start - first - when_evil_lurks.suggestion.runtime)


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_the_floor_set_shows_obrien_nothing_representable_and_bartholomew_no_ballot(db, seeded):
    line, out_for = of_the_roster()

    assert sorted(line["out"]) == [("Bartholomew Winthrop", "no ballot"), ("O'Brien", "nothing representable")]


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.PICK) :], indirect=True)
def test_in_pick_and_run_the_seeded_plan_has_a_floor_above_zero_that_removing_a_pinner_s_film_drops(db, seeded):
    read = plan_load()
    assert read["floor"] > 0 and read["sigma_rep"] > 0

    pinned = {each["film"] for each in read["rows"] if each["pins"]}
    Box.objects.filter(suggestion__title__in=pinned).delete()

    assert plan_load()["floor"] < read["floor"]
