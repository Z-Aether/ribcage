"""The card's one Save: the note, the runtime, the veto and seen it together, all or nothing (#88, #90, #133, #152)."""

from dataclasses import dataclass

from django.db import transaction

from ribcage.ballot import placing
from ribcage.phase.order import Phase
from ribcage.suggestions import notes, runtime, withdrawal

STATES = {"1": True, "0": False}


@dataclass(frozen=True)
class Refusals:
    """What the write refused, each for the box it belongs beside; empty when it saved."""

    note: Exception | None = None
    runtime: str = ""

    def __bool__(self):
        return self.note is not None or bool(self.runtime)


@dataclass(frozen=True)
class Toggles:
    """The veto and seen it a Save carries, each the state the voter set on the card, or None where the card left it as it was (#152)."""

    veto: bool | None = None
    seen: bool | None = None

    @classmethod
    def posted(cls, post):
        """Read from a post: each toggle posts its state and the state the card was drawn with, and one that was not changed is no write, so a page left open never undoes a mark made elsewhere."""
        def changed(name):
            state = STATES.get(post.get(name))
            return state if state is not None and state != STATES.get(post.get(f"{name}_was")) else None

        return cls(veto=changed("veto"), seen=changed("seen"))


def runtime_acts(suggestion, typed, phase):
    """Whether the runtime part is written: the box was open, it is SUGGEST, and nothing holds the film since the page loaded (#27, #34, #90)."""
    return typed is not None and phase is Phase.SUGGEST and withdrawal.withdrawable(suggestion)


def save(suggestion, author, typed_note, typed_runtime, phase, toggles=Toggles()):
    """Write the note, the runtime where `runtime_acts`, and the toggles in one transaction; if the note or the runtime is refused nothing is written.

    `typed_runtime` is None where the box was shut. A runtime for a film approved or held since is dropped without a word (#27, #34).
    The veto is written in SUGGEST and APPROVE alone, scores and VOTE's veto being the placement's; seen it in each, through the one write of each (#10, #152).
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
        else:
            if toggles.veto is not None and phase in (Phase.SUGGEST, Phase.APPROVE):
                placing.set_veto(author, suggestion, toggles.veto)
            if toggles.seen is not None:
                placing.mark_seen(author, suggestion, toggles.seen)
    return found
