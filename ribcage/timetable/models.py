from django.db import models
from django.db.models import Q

SMALLEST_LABELLED_LENGTH = 5
LABEL_LENGTH = 40


class Timetable(models.Model):
    """The marathon's one timetable: its anchor and its budget, both empty until the admin sets them (#12, #36, #135).

    No row means both are empty, so a fresh database needs nothing to set it; `setting.read` is the one way to get it.
    It is no app-state row: the phase stays in its history (#26 §6).
    """

    # An instant; shown in the deployment's one TIME_ZONE, never the device's (#36).
    anchor = models.DateTimeField(null=True)
    # Whole minutes of screen time, and nothing about the wall clock (#12).
    budget = models.PositiveIntegerField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(pk=1), name="one_timetable"),
            models.CheckConstraint(condition=Q(budget__isnull=True) | Q(budget__gt=0), name="a_budget_is_some_minutes"),
        ]


class Box(models.Model):
    """One box on the timetable: a film's, or a labelled one (a break, say), at an offset from the anchor (#12, #22, #26 §8, #135).

    A film box has no length of its own, since its length is always the film's runtime (#22).
    """

    # PROTECT: a hold `withdrawal.withdrawable` misses makes the delete fail instead of cascading (#64, 2026-10-23).
    # Unique, so a film appears on the timetable at most once; a labelled box has none.
    suggestion = models.OneToOneField("suggestions.Suggestion", null=True, on_delete=models.PROTECT, related_name="box")
    label = models.CharField(max_length=LABEL_LENGTH, blank=True)
    length = models.PositiveIntegerField(null=True)
    flexible = models.BooleanField(default=False)
    # Elapsed minutes from the anchor; negative when a push has carried the box before it (#13).
    start = models.IntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(suggestion__isnull=False, label="", length__isnull=True, flexible=False)
                | Q(suggestion__isnull=True, length__isnull=False, length__gte=SMALLEST_LABELLED_LENGTH) & ~Q(label=""),
                name="a_box_is_a_film_or_a_labelled_one",
            ),
        ]
