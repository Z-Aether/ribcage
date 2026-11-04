"""The candidates not yet on the timetable, in slate order, each with what its entry shows (#36, #137)."""

from dataclasses import dataclass

from ribcage.ballot import board
from ribcage.ballot.models import BallotRecord
from ribcage.readouts import slate
from ribcage.readouts.slate import SlateEntry


@dataclass(frozen=True)
class Offered:
    """One entry of *Approved, not in the plan*: the film, its runtime and the initials of those who vetoed it."""

    suggestion: int
    film: object
    runtime: int
    vetoed_by: str
    vetoers: str


def in_slate_order(suggestions):
    """The suggestions `suggestions` in slate order on the stored votes: fewest vetoes first, then most film points, then title (#137, #171)."""
    by_id = {each.pk: each for each in suggestions}
    records = {}
    for suggestion_id, score, vetoed in BallotRecord.objects.filter(suggestion__in=list(by_id)).values_list("suggestion_id", "score", "vetoed"):
        records.setdefault(suggestion_id, []).append((score, vetoed))
    standings = [
        SlateEntry(each.pk, each.title, sum(1 for _, vetoed in records.get(each.pk, ()) if vetoed), slate.film_points(records.get(each.pk, ())))
        for each in by_id.values()
    ]
    return [by_id[standing.key] for standing in slate.slate_order(standings)]


def not_in_the_plan():
    """Approved films with no box, in slate order: three queries however many there are (candidates, records, vetoes)."""
    ordered = in_slate_order(board.candidates().filter(box__isnull=True))
    marks = board.veto_marks(board.vetoes_on([each.pk for each in ordered]), None)
    return [Offered(each.pk, each.film, each.runtime, *marks.get(each.pk, ("", ""))) for each in ordered]
