from django.db import models

from ribcage.phase.order import Phase


class PhaseMove(models.Model):
    """One entry in the phase history: the phase entered, and when. Nothing else stores the phase (#26, #74)."""

    phase = models.CharField(max_length=max(len(phase) for phase in Phase), choices=Phase.choices)
    at = models.DateTimeField()

    class Meta:
        # Appended in order, so the newest move is the highest key whatever the clock said.
        ordering = ["pk"]
