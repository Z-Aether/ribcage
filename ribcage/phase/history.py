from django.db import transaction
from django.utils import timezone

from ribcage.phase.models import PhaseMove
from ribcage.phase.order import Phase, check_move, derived_phase


def current():
    # The newest move alone, as the phase check reads it on every voter write (#74, #78).
    return derived_phase(PhaseMove.objects.order_by("-pk").values_list("phase", flat=True)[:1])


def last_entered():
    """When each phase was last entered, for the phases the history holds; a fresh SUGGEST has no date (#74, #77)."""
    # Oldest first, so each phase keeps its newest move's time, whatever the clock said (#77).
    return {Phase(phase): at for phase, at in PhaseMove.objects.order_by("pk").values_list("phase", "at")}


def move(from_phase, to_phase):
    """The one way the phase moves: one step from the phase the caller believes is current (#15, #28)."""
    # IMMEDIATE transactions take the write lock at BEGIN, so two moves can't both read the same phase (#14, #74).
    with transaction.atomic():
        check_move(current(), from_phase, to_phase)
        return PhaseMove.objects.create(phase=to_phase, at=timezone.now())


def vote_has_opened():
    """Whether the history holds a move into VOTE, so it stays true after a move back to APPROVE (#26 §6, #124)."""
    return PhaseMove.objects.filter(phase=Phase.VOTE).exists()


def reveal_has_happened():
    """Whether the history holds a move into PICK, which opened the scores, so it stays true after a move back to VOTE (#26 §6, #29, #125)."""
    return PhaseMove.objects.filter(phase=Phase.PICK).exists()
