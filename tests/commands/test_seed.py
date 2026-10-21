from io import BytesIO, StringIO, TextIOWrapper

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from ribcage.hello.models import Message
from ribcage.identity.models import Voter

SEEDED_DISPLAY_NAMES = ["Ada", "Anne-Marie", "O'Brien", "Zoë", "Sam", "Bartholomew Winthrop"]
SEEDED_PASSWORD = "popcorn-before-midnight"

# The pages these tests fetch render static tags, which need collectstatic's output with DEBUG off (#46).
pytestmark = pytest.mark.usefixtures("collected_static_files")


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


def test_the_hello_page_shows_the_seeded_messages(transactional_db, debug_on, client):
    call_command("seed")

    page = client.get("/").text

    assert "Popcorn at seven" in page
    assert "Who is bringing the projector?" in page
    assert "Seeded for the local instance" in page


def test_with_debug_off_it_refuses_and_leaves_the_database_alone(transactional_db, settings, client):
    settings.DEBUG = False
    Message.objects.create(text="Written before the seed")

    with pytest.raises(CommandError, match="only with DEBUG on"):
        call_command("seed")

    assert "Written before the seed" in client.get("/").text
    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is None


@pytest.mark.parametrize("phase", ["APPROVE", "VOTE", "PICK", "RUN", "SETUP", "vote"])
def test_any_phase_but_the_fresh_one_is_refused_until_m3_and_the_database_left_alone(
    transactional_db, debug_on, client, phase
):
    Message.objects.create(text="Written before the seed")

    with pytest.raises(CommandError, match="Phases arrive in M3"):
        call_command("seed", "--phase", phase)

    assert "Written before the seed" in client.get("/").text


def test_the_fresh_phase_can_be_named(transactional_db, debug_on):
    call_command("seed", "--phase", "SUGGEST")

    assert authenticate(display_name="Ada", password=SEEDED_PASSWORD) is not None


def seeded_state(client):
    roster = [(voter.pk, voter.display_name) for voter in Voter.objects.order_by("pk")]
    messages = [(message.pk, message.text) for message in client.get("/").context["latest_messages"]]
    return roster, messages


def test_seeding_starts_from_nothing(transactional_db, debug_on, client):
    Voter.objects.create_voter("Interloper")
    Message.objects.create(text="Written before the seed")

    call_command("seed")

    roster, messages = seeded_state(client)
    assert [display_name for _, display_name in roster] == SEEDED_DISPLAY_NAMES
    assert [text for _, text in messages] == [
        "Popcorn at seven",
        "Who is bringing the projector?",
        "Seeded for the local instance",
    ]


def test_seeding_twice_gives_the_same_state(transactional_db, debug_on, client):
    call_command("seed")
    first = seeded_state(client)

    call_command("seed")

    assert seeded_state(client) == first


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
