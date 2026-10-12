import re
from pathlib import Path

import pytest

import ribcage
from ribcage.privacy import POLICY_FILE

# The substance #5, #16 and #30 settled; M10 rewords the policy (#39) and moves these phrases with it.
SETTLED_POINTS = {
    "the display name is the only personal detail": ["display name", "only personal detail"],
    "watched lists exist and are shown to no one else": ["watched list", "shown to no one else"],
    "the admin and the host can read the database": ["the admin and the host can read the database"],
    "everything is deleted at teardown": ["everything the app holds is deleted at teardown"],
    "except the developer's pseudonymised score matrix": [
        "the one exception is a pseudonymised score matrix the developer keeps privately for testing",
    ],
    "the host's proxy may log requests but never what anyone flagged": [
        "the host's own proxy may log requests; those logs never contain what you flagged.",
    ],
    "watched-list topics never appear in a web address": [
        "the topics on your watched list never appear in a web address",
    ],
    "posters load from tmdb, which sees the voter's ip address and which posters load": [
        "posters load in your browser straight from tmdb's image servers",
        "tmdb sees your ip address and which posters your browser loads",
    ],
}


def policy_text():
    return re.sub(r"\s+", " ", POLICY_FILE.read_text(encoding="utf-8")).lower()


@pytest.mark.parametrize("phrases", SETTLED_POINTS.values(), ids=SETTLED_POINTS.keys())
def test_the_policy_states_each_settled_point(phrases):
    text = policy_text()

    assert [phrase for phrase in phrases if phrase not in text] == []


def test_the_policy_ships_inside_the_app_package():
    # The image's allowlist takes the package, so a policy kept inside it ships too (#49, #51).
    assert POLICY_FILE.is_relative_to(Path(ribcage.__file__).parent)
