"""The ballot as a voter sees it: the Unsorted tray and the five bands, plain data for the board's template (#9, #38, #119)."""

from dataclasses import dataclass

from ribcage.ballot import order
from ribcage.ballot.models import BallotRecord
from ribcage.films.film import Film
from ribcage.suggestions.models import Approval, Suggestion
from ribcage.triggers import stored, watched

# Each band: the score it sets, its key for the style, its sign and its name; the wording waits for M10's copy pass (#39, #119).
SCALE = (
    (3, "top-pick", "+3", "Top pick"),
    (2, "keen", "+2", "Keen"),
    (1, "happy", "+1", "Happy to watch"),
    (0, "dont-mind", "0", "Don't mind"),
    (-1, "rather-not", "−1", "Rather not"),
)


@dataclass(frozen=True)
class Tile:
    suggestion_id: int
    film: Film
    # The ring's own count, `Matched.strong`; zero where the ring is absent (#117).
    trigger_count: int = 0
    seen_it: bool = False
    vetoed_by: str = ""
    caption: str = ""


@dataclass(frozen=True)
class Band:
    score: int
    key: str
    sign: str
    name: str
    tiles: tuple[Tile, ...] = ()


@dataclass(frozen=True)
class Counts:
    # How many candidates are out of Unsorted, vetoed ones included, out of the ballot's size (#63, #119).
    scored: int
    size: int

    @property
    def left(self):
        return self.size - self.scored


@dataclass(frozen=True)
class Board:
    tray: tuple[Tile, ...]
    bands: tuple[Band, ...]
    counts: Counts
    # Where a placement posts; the gallery's board has none, so dragging there writes nothing.
    places_at: str = ""


def candidates():
    """The ballot is exactly the approved suggestions; a dropped film's records are kept but unseen (#15, #28, #119)."""
    return Suggestion.objects.filter(approval=Approval.APPROVED)


def records_of(viewer):
    """The viewer's records on the candidates, as (score, vetoed) by suggestion (#119)."""
    return {
        suggestion_id: (score, vetoed)
        for suggestion_id, score, vetoed in BallotRecord.objects.filter(voter=viewer, suggestion__approval=Approval.APPROVED).values_list("suggestion_id", "score", "vetoed")
    }


def is_placed(record):
    """The one rule for a film being out of Unsorted: a record with a score or a veto; a record holding only seen-it is not (#119)."""
    return record is not None and (record[0] is not None or record[1])


def of(viewer, places_at=""):
    """The viewer's ballot, loading every tile's match at once so the query count never grows with it (#111)."""
    suggestions = list(candidates())
    records = records_of(viewer)
    loaded = stored.sections_and_matches_of(suggestions, watched.ticked_ids(viewer))
    by_id = {suggestion.pk: suggestion for suggestion in suggestions}

    def tile(suggestion_id):
        matched = loaded[suggestion_id][1]
        count = matched.strong if matched is not None and matched.ring else 0
        return Tile(suggestion_id, by_id[suggestion_id].film, trigger_count=count)

    def score_of(suggestion_id):
        return records.get(suggestion_id, (None, False))[0]

    unplaced = [pk for pk in by_id if not is_placed(records.get(pk))]
    matched_ids = {pk for pk in unplaced if loaded[pk][1] is not None}
    tray = tuple(tile(pk) for pk in order.tray_order(viewer.pk, unplaced, matched_ids))
    bands = tuple(
        Band(score, key, sign, name, tuple(tile(pk) for pk in order.shuffled(viewer.pk, [pk for pk in by_id if score_of(pk) == score])))
        for score, key, sign, name in SCALE
    )
    # A vetoed film is out of Unsorted and in no band: the Veto band holds it (#120).
    return Board(tray, bands, Counts(sum(is_placed(record) for record in records.values()), len(by_id)), places_at=places_at)


def counts_of(viewer):
    """What a placement's answer updates, without loading a tile: the same rule as `of`, so the header reads alike after a reload (#119)."""
    return Counts(sum(is_placed(record) for record in records_of(viewer).values()), candidates().count())
