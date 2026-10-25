"""A voter's watched list is never rendered to anyone else, the admin included (#20 section 5, #113).

By difference, since topic names appear legitimately wherever a film's topic list does: every page and card fragment is rendered as another voter and as the admin
with the owner's list ticked, empty and under *I don't care*, in each phase from SUGGEST to PICK, and the renders must be identical. A surface a later ticket
adds to `routes.py` is swept without changing this file, and fails here if it prints anything derived from the owner's list. Nothing is aggregated either:
a count of who watches a topic is a difference between the states like any other.
"""

import difflib
import re

import pytest
from django.db import transaction
from django.test import Client

from ribcage.phase.order import Phase
from ribcage.suggestions.models import Approval
from ribcage.triggers import client as dtdd_client
from ribcage.triggers import correction, stored, watched
from tests.dtdd import Dtdd, detail, item
from tests.http.routes import ADMIN, VOTER
from tests.http.signing_in import sign_in_as_the_admin
from tests.http.sweeping import CAT, DOG, JUMP, NO, RECORD, YES, add, sentinel_vocabulary, sweep
from tests.http.test_phase import walk_to

PHASES = [Phase.SUGGEST, Phase.APPROVE, Phase.VOTE, Phase.PICK]
TICKED, EMPTY, DOES_NOT_CARE = "ticked", "empty", "does not care"
# What two renders of one state differ by, and nothing else is forgiven: Django masks the CSRF token afresh on every render, and a signed snapshot carries its signing time.
NORMALISED = [
    (re.compile(r'(name="csrfmiddlewaretoken" value=")[^"]*'), r"\1CSRF"),
    (re.compile(r'(&quot;X-CSRFToken&quot;: &quot;|"X-CSRFToken": ")[^"&]*'), r"\1CSRF"),
    (re.compile(r'(name="snapshot" value=")[^"]*'), r"\1SIGNED"),
]


def normalised(text):
    for pattern, replacement in NORMALISED:
        text = pattern.sub(replacement, text)
    return text


def put_list(owner, state):
    if state == TICKED:
        watched.set_ticked(owner, CAT, True)
        watched.set_ticked(owner, JUMP, True)
    elif state == DOES_NOT_CARE:
        watched.stop_caring(owner)


@pytest.fixture
def cast(voters, monkeypatch, clock):
    """The clock stands still, so the renders' times agree; the owner, whose list varies; an observer who watches the dog themselves, so the owner's other topics would show as a difference; one with no list and *I don't care* off, who is shown what only the undecided see, the nag bar among it; the admin; and four films."""
    stored.replace_vocabulary(dtdd_client.Client("key", Dtdd(vocabulary=sentinel_vocabulary())).vocabulary().value)
    ada, observer, undecided, owner = voters["ada"], voters["Hanna"], voters["ada"], voters["Dani"]
    # Counts high enough to ring a film for whoever watches its topics (#109).
    films = [add(ada, title, approval, yes=40, no=3) for title, approval in (("Undecided", Approval.UNDECIDED), ("Approved", Approval.APPROVED), ("Dropped", Approval.DROPPED))]
    films.append(add(ada, "By hand", Approval.UNDECIDED, counted=False))
    watched.set_ticked(observer, DOG, True)
    previewed = Dtdd(details=[detail(item(9001, f"{RECORD}previewed", 2002), (DOG, YES, NO), (CAT, YES, NO))])
    monkeypatch.setattr(correction, "dtdd_client", lambda: dtdd_client.Client("key", previewed))
    clients = {name: Client() for name in ("observer", "undecided", "owner", ADMIN)}
    clients["observer"].force_login(observer)
    clients["undecided"].force_login(undecided)
    clients["owner"].force_login(owner)
    sign_in_as_the_admin(clients[ADMIN])
    return {"owner": owner, "films": films, "clients": clients}


def renders(cast, phase, state, as_the="observer"):
    """Everything the sweep meets in `phase` with the owner's list in `state`, keyed by what was asked, from a pool rolled back afterwards so each render starts from the same one."""
    owner, clients = cast["owner"], cast["clients"]
    viewers = {VOTER: clients[as_the], ADMIN: clients[ADMIN]}
    with transaction.atomic():
        walk_to(phase)
        put_list(owner, state)
        # The Roster's remove confirm for the owner, which says nothing of their list (#107).
        answers = list(sweep(viewers, cast["films"], also=[(f"/console/roster/?remove={owner.pk}", ADMIN)]))
        transaction.set_rollback(True)
    return [(answer.where, (answer.status, answer.headers, normalised(answer.text))) for answer in answers]


def differences(before, after):
    """What differs between two lists of renders, as readable lines; an answer present in only one is itself a difference."""
    assert [where for where, _ in before] == [where for where, _ in after]
    found = []
    for (where, one), (_, other) in zip(before, after):
        if one != other:
            lines = difflib.unified_diff(one[2].splitlines(), other[2].splitlines(), lineterm="", n=0)
            found.append(f"{where}: status {one[0]} / {other[0]}; headers {sorted(set(one[1]) ^ set(other[1]))}; " + " | ".join(list(lines)[2:8]))
    return found


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("observer", ["observer", "undecided"])
def test_no_page_or_fragment_shown_to_another_voter_or_the_admin_differs_with_the_owners_list(cast, phase, observer):
    empty = renders(cast, phase, EMPTY, as_the=observer)

    assert differences(empty, renders(cast, phase, TICKED, as_the=observer)) == []
    assert differences(empty, renders(cast, phase, DOES_NOT_CARE, as_the=observer)) == []


def test_the_sweep_is_not_vacuous_and_two_renders_of_one_state_agree_once_tokens_are_normalised(cast):
    first, second = renders(cast, Phase.VOTE, TICKED), renders(cast, Phase.VOTE, TICKED)

    assert differences(first, second) == []
    wheres = [where for where, _ in first]
    assert f"{ADMIN} /console/roster/?remove={cast['owner'].pk}" in wheres
    assert f"{VOTER} /" in wheres and f"{VOTER} /warnings/" in wheres and f"{ADMIN} /console/films/" in wheres
    assert len(wheres) > 40
    # Raw, the renders differ by their tokens alone: the normalising forgives nothing else.
    with transaction.atomic():
        walk_to(Phase.VOTE)
        raw = [a.text for a in sweep({VOTER: cast["clients"]["observer"], ADMIN: cast["clients"][ADMIN]}, cast["films"])]
        transaction.set_rollback(True)
    assert any(normalised(text) != text for text in raw)


@pytest.mark.parametrize("phase", PHASES)
def test_the_owners_own_pool_and_warnings_do_differ_between_the_states(cast, phase):
    """The control: with the same sweep from the owner's side, their list shows on their own pages, so a pass above is not a broken fixture (#113)."""
    own = {state: {where: render[2] for where, render in renders(cast, phase, state, as_the="owner")} for state in (EMPTY, TICKED, DOES_NOT_CARE)}

    pages = [f"{VOTER} /warnings/"] + ([f"{VOTER} /"] if phase is not Phase.PICK else [])
    for page in pages:
        assert own[EMPTY][page] != own[TICKED][page], page
        assert own[EMPTY][page] != own[DOES_NOT_CARE][page], page
    # The pool's cards are shown in SUGGEST and APPROVE alone until M6's ballot, and they ring from the list.
    if phase in (Phase.SUGGEST, Phase.APPROVE):
        assert own[EMPTY][f"{VOTER} /"].count("has-trigger-icon") < own[TICKED][f"{VOTER} /"].count("has-trigger-icon")
