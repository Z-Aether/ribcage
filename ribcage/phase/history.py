from django.db import transaction
from django.utils import timezone

from ribcage.phase.models import PhaseMove
from ribcage.phase.order import check_move, derived_phase


def current():
    return derived_phase(PhaseMove.objects.values_list("phase", flat=True))


def move(from_phase, to_phase):
    """The one way the phase moves: one step from the phase the caller believes is current (#15, #28)."""
    # IMMEDIATE transactions take the write lock at BEGIN, so two moves can't both read the same phase (#14, #74).
    with transaction.atomic():
        check_move(current(), from_phase, to_phase)
        return PhaseMove.objects.create(phase=to_phase, at=timezone.now())
