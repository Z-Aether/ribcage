"""The card's one Save: the note and the runtime together, all or nothing (#88, #90, #133)."""

from dataclasses import dataclass

from django.db import transaction

from ribcage.phase.order import Phase
from ribcage.suggestions import notes, runtime, withdrawal


@dataclass(frozen=True)
class Refusals:
    """What the write refused, each for the box it belongs beside; empty when it saved."""

    note: Exception | None = None
    runtime: str = ""

    def __bool__(self):
        return self.note is not None or bool(self.runtime)


def runtime_acts(suggestion, typed, phase):
    """Whether the runtime part is written: the box was open, it is SUGGEST, and nothing holds the film since the page loaded (#27, #34, #90)."""
    return typed is not None and phase is Phase.SUGGEST and withdrawal.withdrawable(suggestion)


def save(suggestion, author, typed_note, typed_runtime, phase):
    """Write the note, and the runtime where `runtime_acts`, in one transaction; if either is refused neither is written.

    `typed_runtime` is None where the box was shut. A runtime for a film approved or held since is dropped without a word (#27, #34).
    """
    refusals = {}
    with transaction.atomic():
        try:
            notes.write(suggestion, author, typed_note)
        except (notes.TooLong, notes.PitchRequired) as refused:
            refusals["note"] = refused
        if runtime_acts(suggestion, typed_runtime, phase):
            try:
                runtime.correct(suggestion, typed_runtime)
            except runtime.Refused as refused:
                refusals["runtime"] = str(refused)
        found = Refusals(**refusals)
        if found:
            transaction.set_rollback(True)
    return found
