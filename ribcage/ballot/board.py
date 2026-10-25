"""The ballot as a voter sees it: the Unsorted tray and the five bands, plain data for the board's template (#9, #38, #119)."""

from dataclasses import dataclass

from ribcage.ballot import order
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import Matched
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
    # One initial per other voter who vetoed it, and their names for the hover (#120).
    vetoed_by: str = ""
    vetoers: str = ""
    caption: str = ""
    # What the viewer's Veto row shows: their matched topics, their reason, and what saving it said (#120).
    matched: Matched | None = None
    reason: str = ""
    said: str = ""
    refused: bool = False


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
    # The viewer's own vetoes, each a widened row (#120).
    vetoes: tuple[Tile, ...] = ()
    # Where a placement posts; the gallery's board has none, so dragging there writes nothing.
    places_at: str = ""

    @property
    def inert(self):
        return not self.places_at


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


def vetoes_on(candidate_ids):
    """Every voter's vetoes on the candidates, in one query: (suggestion, voter, name, reason) rows (#9, #120)."""
    return BallotRecord.objects.filter(vetoed=True, suggestion__in=candidate_ids).values_list("suggestion_id", "voter_id", "voter__display_name", "veto_reason")


def veto_marks(rows, viewer):
    """What the other voters' vetoes put on a tile: their initials and their names, by suggestion, sorted by name (#120)."""
    names = {}
    for suggestion_id, voter_id, name, _ in rows:
        if voter_id != viewer.pk:
            names.setdefault(suggestion_id, []).append(name)
    return {
        suggestion_id: ("".join(name.strip()[:1].upper() for name in sorted(each)), "Vetoed by " + ", ".join(sorted(each))) for suggestion_id, each in names.items()
    }


def tile_of(suggestion, matched, marks, reasons):
    """One tile: the ring's count where the film rings, the others' ribbon, and the viewer's own veto row's data (#117, #120)."""
    initials, names = marks.get(suggestion.pk, ("", ""))
    count = matched.strong if matched is not None and matched.ring else 0
    return Tile(suggestion.pk, suggestion.film, trigger_count=count, vetoed_by=initials, vetoers=names, matched=matched, reason=reasons.get(suggestion.pk, ""))


def of(viewer, places_at=""):
    """The viewer's ballot, loading every tile's match at once so the query count never grows with it (#111)."""
    suggestions = list(candidates())
    records = records_of(viewer)
    loaded = stored.sections_and_matches_of(suggestions, watched.ticked_ids(viewer))
    by_id = {suggestion.pk: suggestion for suggestion in suggestions}
    rows = list(vetoes_on(list(by_id)))
    marks = veto_marks(rows, viewer)
    reasons = {suggestion_id: reason or "" for suggestion_id, voter_id, _, reason in rows if voter_id == viewer.pk}

    def tile(suggestion_id):
        return tile_of(by_id[suggestion_id], loaded[suggestion_id][1], marks, reasons)

    def score_of(suggestion_id):
        return records.get(suggestion_id, (None, False))[0]

    unplaced = [pk for pk in by_id if not is_placed(records.get(pk))]
    matched_ids = {pk for pk in unplaced if loaded[pk][1] is not None}
    tray = tuple(tile(pk) for pk in order.tray_order(viewer.pk, unplaced, matched_ids))
    bands = tuple(
        Band(score, key, sign, name, tuple(tile(pk) for pk in order.shuffled(viewer.pk, [pk for pk in by_id if score_of(pk) == score])))
        for score, key, sign, name in SCALE
    )
    vetoes = tuple(tile(pk) for pk in order.shuffled(viewer.pk, list(reasons)))
    return Board(tray, bands, Counts(sum(is_placed(record) for record in records.values()), len(by_id)), vetoes, places_at=places_at)


def one_tile(viewer, suggestion):
    """A single tile as `of` draws it, for an answer that puts it somewhere new or redraws its row (#120)."""
    ((_, matched),) = stored.sections_and_matches_of([suggestion], watched.ticked_ids(viewer)).values()
    rows = list(vetoes_on([suggestion.pk]))
    reasons = {suggestion.pk: reason or "" for _, voter_id, _, reason in rows if voter_id == viewer.pk}
    return tile_of(suggestion, matched, veto_marks(rows, viewer), reasons)


def counts_of(viewer):
    """What a placement's answer updates, without loading a tile: the same rule as `of`, so the header reads alike after a reload (#119)."""
    return Counts(sum(is_placed(record) for record in records_of(viewer).values()), candidates().count())
