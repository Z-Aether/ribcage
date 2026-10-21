from typing import NamedTuple

from django.db import models


class Phase(models.TextChoices):
    """The five phases, in the order the marathon walks them (#15)."""

    SUGGEST = "SUGGEST", "SUGGEST"
    APPROVE = "APPROVE", "APPROVE"
    VOTE = "VOTE", "VOTE"
    PICK = "PICK", "PICK"
    RUN = "RUN", "RUN"


# A fresh database starts here: standing the app up is the deployment's business (#15).
FRESH_PHASE = Phase.SUGGEST
PHASES = list(Phase)


class Neighbours(NamedTuple):
    back: Phase | None
    forward: Phase | None


class MoveRefused(Exception):
    pass


def neighbours(phase):
    index = PHASES.index(phase)
    return Neighbours(
        back=PHASES[index - 1] if index > 0 else None,
        forward=PHASES[index + 1] if index + 1 < len(PHASES) else None,
    )


def derived_phase(history):
    """The phase the history, oldest move first, leaves the marathon in."""
    entered = list(history)
    return Phase(entered[-1]) if entered else FRESH_PHASE


def check_move(current, from_phase, to_phase):
    # The caller names the phase it believes is current, so a stale caller can't skip a step (#74).
    if from_phase != current:
        raise MoveRefused(f"The phase is {current}, not {from_phase}.")
    if to_phase is None or to_phase not in neighbours(from_phase):
        raise MoveRefused(f"{from_phase} moves only one step, not to {to_phase}.")
