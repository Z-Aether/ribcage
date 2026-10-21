from io import BytesIO, StringIO, TextIOWrapper

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command
from django.utils import timezone

from ribcage.identity.models import Voter
from ribcage.phase.history import current
from ribcage.phase.models import PhaseMove
from ribcage.phase.order import PHASES, Phase

SEEDED_DISPLAY_NAMES = ["Ada", "Anne-Marie", "O'Brien", "Zoë", "Sam", "Bartholomew Winthrop"]
SEEDED_PASSWORD = "popcorn-before-midnight"

@pytest.fixture(autouse=True)
def fast_hashing(settings):
    # The default hasher costs about a second per check, and hashing is Django's to test.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.mark.parametrize("display_name", SEEDED_DISPLAY_NAMES)
def test_every_seeded_voter_signs_in_with_the_known_password(transactional_db, debug_on, display_name):
    call_command("seed")

    voter = authenticate(display_name=display_name, password=SEEDED_PASSWORD)

    assert voter is not None
    assert voter.display_name == display_name


def test_with_debug_off_it_refuses_and_leaves_the_database_alone(transactional_db, settings):
    settings.DEBUG = False
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seed")

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]
    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is None


@pytest.mark.parametrize("phase", ["SETUP", "vote", "Suggest", "", "SOLVE"])
def test_anything_but_the_five_phases_is_refused_and_the_database_left_alone(transactional_db, debug_on, phase):
    Voter.objects.create_voter("Before the seed")

    with pytest.raises(CommandError, match="invalid choice"):
        call_command("seed", "--phase", phase)

    assert list(Voter.objects.values_list("display_name", flat=True)) == ["Before the seed"]


def test_with_no_phase_named_it_seeds_a_fresh_suggest_with_no_history(transactional_db, debug_on):
    call_command("seed")

    assert current() is Phase.SUGGEST
    assert not PhaseMove.objects.exists()


@pytest.mark.parametrize("phase", PHASES)
def test_each_phase_lands_there_by_a_walk_one_step_at_a_time(transactional_db, debug_on, phase):
    call_command("seed", "--phase", phase)

    walk = list(PhaseMove.objects.order_by("pk"))
    assert current() is phase
    assert [move.phase for move in walk] == PHASES[1 : PHASES.index(phase) + 1]
    assert [move.at for move in walk] == sorted(move.at for move in walk)
    assert all(move.at < timezone.now() for move in walk)
    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is not None


def test_the_output_names_the_seeded_phase(transactional_db, debug_on):
    output = StringIO()

    call_command("seed", "--phase", "PICK", stdout=output)

    assert "Seeded PICK" in output.getvalue()


def seeded_state():
    return [(voter.pk, voter.display_name) for voter in Voter.objects.order_by("pk")]


def test_seeding_starts_from_nothing(transactional_db, debug_on):
    Voter.objects.create_voter("Interloper")

    call_command("seed")

    assert [display_name for _, display_name in seeded_state()] == SEEDED_DISPLAY_NAMES


def test_seeding_twice_gives_the_same_state(transactional_db, debug_on):
    call_command("seed")
    first = seeded_state()

    call_command("seed")

    assert seeded_state() == first


def test_the_output_names_every_seeded_voter_and_the_password(transactional_db, debug_on):
    output = StringIO()

    call_command("seed", stdout=output)

    assert all(display_name in output.getvalue() for display_name in SEEDED_DISPLAY_NAMES)
    assert SEEDED_PASSWORD in output.getvalue()


def test_the_voter_list_reaches_a_redirected_cp1252_stdout_as_utf8(transactional_db, debug_on):
    redirected = TextIOWrapper(BytesIO(), encoding="cp1252")

    call_command("seed", stdout=redirected)

    redirected.flush()
    assert "Zoë" in redirected.buffer.getvalue().decode("utf-8")
