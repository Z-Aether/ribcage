from django.conf import settings
from django.db import models
from django.db.models import Q

LOWEST_SCORE = -1
HIGHEST_SCORE = 3


class BallotRecord(models.Model):
    """One voter's say on one film: a score or a veto, and whether they have seen it (#26 §4, #118).

    A veto's reason is the voter's note on the film, kept as a note is, not a field here (#63, #128).
    No record means untouched. A write that leaves a record with no score, no veto and no seen it deletes it.
    Only a score holds its film: a veto or seen it alone goes with a withdraw (#63, #118, #151).
    """

    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ballot_records")
    # PROTECT: a hold `withdrawal.withdrawable` misses makes the delete fail instead of cascading (#63, 2026-10-23).
    suggestion = models.ForeignKey("suggestions.Suggestion", on_delete=models.PROTECT, related_name="ballot_records")
    score = models.SmallIntegerField(null=True)
    # A veto is its own field, never a step on the scale: its -2 is derived, never stored as a score (#10, #26 §4).
    vetoed = models.BooleanField(default=False)
    seen_it = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("voter", "suggestion"), name="one_record_per_voter_per_suggestion"),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=LOWEST_SCORE, score__lte=HIGHEST_SCORE),
                name="score_is_on_the_scale",
            ),
            models.CheckConstraint(condition=~Q(vetoed=True) | Q(score__isnull=True), name="a_veto_has_no_score"),
        ]


class DoneMarker(models.Model):
    """A voter saying they have finished with the ballot; one per voter, and its absence means not done (#15, #26)."""

    voter = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="done_marker")
