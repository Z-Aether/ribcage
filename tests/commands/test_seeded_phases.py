from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command
from django.db.models import F
from django.test import override_settings
from django.utils import timezone

from ribcage.ballot.models import BallotRecord, DoneMarker
from ribcage.films.corpus import read_entries
from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import PHASES, Phase
from ribcage.suggestions.models import Approval, Note, Suggestion
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
def test_before_vote_nobody_has_a_ballot(db, seeded):
    assert not BallotRecord.objects.exists() and not DoneMarker.objects.exists()


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
def test_from_vote_on_some_vetoes_have_reasons_one_has_none_and_one_film_is_vetoed_by_two(db, seeded):
    vetoes = BallotRecord.objects.filter(vetoed=True)

    assert vetoes.filter(veto_reason__isnull=False).count() >= 2
    assert vetoes.filter(veto_reason__isnull=True).count() == 1
    assert vetoes.filter(score__isnull=False).count() == 0
    assert max(vetoes.filter(suggestion=suggestion).count() for suggestion in Suggestion.objects.filter(ballot_records__vetoed=True)) == 2


@pytest.mark.parametrize("seeded", PHASES[PHASES.index(Phase.VOTE) :], indirect=True)
def test_from_vote_on_some_films_are_seen_one_seen_and_scored_and_one_seen_and_vetoed(db, seeded):
    seen = BallotRecord.objects.filter(seen_it=True)

    assert seen.count() >= 3
    assert seen.filter(score__isnull=False).exists() and seen.filter(vetoed=True).exists()
