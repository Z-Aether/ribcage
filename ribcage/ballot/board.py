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


# The data-place of the tray and of the Veto band; a band's is its score (#119, #120).
TRAY = "unsorted"
VETOES = "veto"


@dataclass(frozen=True)
class Tile:
    suggestion_id: int
    film: Film
    # The ring's own count, `Matched.strong`; zero where the ring is absent (#117).
    trigger_count: int = 0
    # The viewer's own seen it, which greys the poster; no one else's ever reaches a tile (#10, #35, #121).
    seen_it: bool = False
    # One initial per other voter who vetoed it, and their names for the hover (#120).
    vetoed_by: str = ""
    vetoers: str = ""
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
    # The viewer's own vetoes, each the same tile as in any band (#120).
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
    """The viewer's records on the candidates, as (score, vetoed, seen it) by suggestion (#119, #121)."""
    return {
        suggestion_id: (score, vetoed, seen_it)
        for suggestion_id, score, vetoed, seen_it in BallotRecord.objects.filter(voter=viewer, suggestion__approval=Approval.APPROVED).values_list(
            "suggestion_id", "score", "vetoed", "seen_it"
        )
    }


def is_placed(record):
    """The one rule for a film being out of Unsorted: a record with a score or a veto; a record holding only seen-it is not (#119)."""
    return record is not None and (record[0] is not None or record[1])


def vetoes_on(candidate_ids):
    """Every voter's vetoes on the candidates, in one query: (suggestion, voter, name) rows (#9, #120)."""
    return BallotRecord.objects.filter(vetoed=True, suggestion__in=candidate_ids).values_list("suggestion_id", "voter_id", "voter__display_name")


def veto_marks(rows, viewer):
    """What the other voters' vetoes put on a tile: their initials and their names, by suggestion, sorted by name (#120).

    The admin has no ballot, so `viewer=None` marks everyone's, as the timetable's boxes do (#136).
    """
    names = {}
    for suggestion_id, voter_id, name in rows:
        if viewer is None or voter_id != viewer.pk:
            names.setdefault(suggestion_id, []).append(name)
    return {
        suggestion_id: ("".join(name.strip()[:1].upper() for name in sorted(each)), "Vetoed by " + ", ".join(sorted(each))) for suggestion_id, each in names.items()
    }


def tile_of(suggestion, matched, marks, seen_it=False):
    """One tile: the ring's count where the film rings, and the others' ribbon (#117, #120)."""
    initials, names = marks.get(suggestion.pk, ("", ""))
    count = matched.strong if matched is not None and matched.ring else 0
    return Tile(suggestion.pk, suggestion.film, trigger_count=count, vetoed_by=initials, vetoers=names, seen_it=seen_it)


def matched_ids(loaded):
    """The ids of the films the viewer matches, out of `sections_and_matches_of`'s answer: the one rule the tray's order reads (#38, #111, #122)."""
    return {pk for pk, (_, matched) in loaded.items() if matched is not None}


def arranged(viewer, ids, records, matched_ids):
    """The ids of every list the board has, in the order it draws them: the tray, each band by score and the Veto band (#38, #119, #120)."""
    unplaced = [pk for pk in ids if not is_placed(records.get(pk))]
    lists = {TRAY: order.tray_order(viewer.pk, unplaced, matched_ids)}
    for score, *_ in SCALE:
        lists[score] = order.shuffled(viewer.pk, [pk for pk in ids if records.get(pk, (None,))[0] == score])
    lists[VETOES] = order.shuffled(viewer.pk, [pk for pk in ids if records.get(pk, (None, False))[1]])
    return lists


def standing(viewer, suggestion):
    """Where the film's tile stands on the viewer's board now: its list's data-place and the id of the tile before it, or None at the head (#122)."""
    ids = list(candidates().values_list("pk", flat=True))
    records = records_of(viewer)
    record = records.get(suggestion.pk)
    place = VETOES if record and record[1] else record[0] if is_placed(record) else TRAY
    loaded = stored.sections_and_matches_of(list(candidates()), watched.ticked_ids(viewer))
    listed = arranged(viewer, ids, records, matched_ids(loaded))[place]
    at = listed.index(suggestion.pk)
    return place, listed[at - 1] if at else None


def of(viewer, places_at=""):
    """The viewer's ballot, loading every tile's match at once so the query count never grows with it (#111)."""
    suggestions = list(candidates())
    records = records_of(viewer)
    loaded = stored.sections_and_matches_of(suggestions, watched.ticked_ids(viewer))
    by_id = {suggestion.pk: suggestion for suggestion in suggestions}
    rows = list(vetoes_on(list(by_id)))
    marks = veto_marks(rows, viewer)

    def tile(suggestion_id):
        return tile_of(by_id[suggestion_id], loaded[suggestion_id][1], marks, records.get(suggestion_id, (None, False, False))[2])

    lists = arranged(viewer, list(by_id), records, matched_ids(loaded))
    tray = tuple(tile(pk) for pk in lists[TRAY])
    bands = tuple(Band(score, key, sign, name, tuple(tile(pk) for pk in lists[score])) for score, key, sign, name in SCALE)
    vetoes = tuple(tile(pk) for pk in lists[VETOES])
    return Board(tray, bands, Counts(sum(is_placed(record) for record in records.values()), len(by_id)), vetoes, places_at=places_at)


def one_tile(viewer, suggestion):
    """A single tile as `of` draws it, for an answer that puts it somewhere new or draws it again (#120)."""
    ((_, matched),) = stored.sections_and_matches_of([suggestion], watched.ticked_ids(viewer)).values()
    rows = list(vetoes_on([suggestion.pk]))
    seen_it = BallotRecord.objects.filter(voter=viewer, suggestion=suggestion, seen_it=True).exists()
    return tile_of(suggestion, matched, veto_marks(rows, viewer), seen_it)


def counts_of(viewer):
    """What a placement's answer updates, without loading a tile: the same rule as `of`, so the header reads alike after a reload (#119)."""
    return Counts(sum(is_placed(record) for record in records_of(viewer).values()), candidates().count())
