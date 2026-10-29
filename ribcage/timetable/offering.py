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


def not_in_the_plan():
    """Approved films with no box, in slate order: three queries however many there are (candidates, records, vetoes)."""
    films = list(board.candidates().filter(box__isnull=True))
    ids = [each.pk for each in films]
    records = {}
    for suggestion_id, score, vetoed in BallotRecord.objects.filter(suggestion__in=ids).values_list("suggestion_id", "score", "vetoed"):
        records.setdefault(suggestion_id, []).append((score, vetoed))
    marks = board.veto_marks(board.vetoes_on(ids), None)
    by_id = {each.pk: each for each in films}
    standings = [
        SlateEntry(each.pk, each.title, sum(1 for _, vetoed in records.get(each.pk, ()) if vetoed), slate.film_points(records.get(each.pk, ())))
        for each in films
    ]
    offered = []
    for standing in slate.slate_order(standings):
        suggestion = by_id[standing.key]
        initials, names = marks.get(suggestion.pk, ("", ""))
        offered.append(Offered(suggestion.pk, suggestion.film, suggestion.runtime, initials, names))
    return offered
