"""The reveal's matrix: every voter's score on every film of the ballot, plain data for `components/reveal.html` from one loader (#29, #154).

#157 sorts it, #158 opens a card under a row and #161 draws it again behind the evening, so the page's view only calls `load`.
"""

from dataclasses import dataclass

from ribcage.ballot import board, progress
from ribcage.ballot.models import BallotRecord
from ribcage.films.film import Film
from ribcage.readouts.placement import is_placed
from ribcage.readouts.slate import film_points
from ribcage.suggestions.models import Note

# A blank is never a 0: the solver counts it as one, the voter did not choose it (#10, #29).
BLANK_WORDS = "no score, counts 0"
SHADES = 8


@dataclass(frozen=True)
class Cell:
    # A score band's key from `board.SCALE`, or "veto", or "blank".
    key: str
    sign: str
    seen_it: bool
    # In the viewer's own column, which is faintly tinted (#29).
    mine: bool
    # The voter's note on the film, a veto's reason; shown on hover (#128).
    reason: str
    meaning: str


@dataclass(frozen=True)
class Column:
    voter_id: int
    name: str
    initial: str
    shade: int
    mine: bool
    # No score and no veto on any film of the ballot: the floor set's *no ballot* test (#29, #33).
    didnt_vote: bool
    # *24 of 32* for a voter who has placed some films but not all, else empty.
    partial: str


@dataclass(frozen=True)
class Row:
    suggestion_id: int
    film: Film
    points: int
    # The points bar's length as a share of the longest, 0 to 100, and which way it points.
    bar: int
    negative: bool
    vetoers: str
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Reveal:
    columns: tuple[Column, ...]
    rows: tuple[Row, ...]
    size: int
    # The score bands, for the legend: (score, key, sign, name).
    scale: tuple = board.SCALE


def cell_of(name, mine, record, reason):
    score, vetoed, seen_it = record if record else (None, False, False)
    if vetoed:
        return Cell("veto", "☒", seen_it, mine, reason, f"{name} vetoed it" + (f": {reason}" if reason else ""))
    for each, key, sign, words in board.SCALE:
        if score == each:
            return Cell(key, sign, seen_it, mine, "", f"{name}: {words}")
    return Cell("blank", "", seen_it, mine, "", f"{name}: {BLANK_WORDS}")


def build(voters, films, records, reasons, viewer_id):
    """The matrix from plain data.

    `voters` is (id, name, scored) in the Roster's order, `films` is (suggestion id, Film) for the ballot,
    `records` is (voter id, suggestion id, score, vetoed, seen it) and `reasons` is {(voter id, suggestion id): the note}.
    """
    size = len(films)
    held = {(voter_id, suggestion_id): (score, vetoed, seen_it) for voter_id, suggestion_id, score, vetoed, seen_it in records}
    columns = tuple(
        Column(
            voter_id,
            name,
            name.strip()[:1].upper(),
            voter_id % SHADES,
            voter_id == viewer_id,
            didnt_vote=not any(is_placed(held.get((voter_id, suggestion_id))) for suggestion_id, _ in films),
            partial=f"{scored} of {size}" if 0 < scored < size else "",
        )
        for voter_id, name, scored in voters
    )
    standing = []
    for suggestion_id, film in films:
        each = [held.get((voter_id, suggestion_id)) for voter_id, _, _ in voters]
        points = film_points((score, vetoed) for score, vetoed, _ in (record or (None, False, False) for record in each))
        cells = tuple(cell_of(name, voter_id == viewer_id, record, reasons.get((voter_id, suggestion_id), "")) for (voter_id, name, _), record in zip(voters, each, strict=True))
        vetoers = ", ".join(name for (_, name, _), record in zip(voters, each, strict=True) if record and record[1])
        standing.append((suggestion_id, film, points, vetoers, cells))
    longest = max((abs(points) for _, _, points, _, _ in standing), default=0) or 1
    rows = tuple(
        Row(suggestion_id, film, points, round(100 * abs(points) / longest), points < 0, vetoers, cells)
        for suggestion_id, film, points, vetoers, cells in sorted(standing, key=lambda each: (-each[2], each[1].title.casefold(), each[1].title, each[0]))
    )
    return Reveal(columns, rows, size)


def load(viewer):
    """The reveal over the ballot as it stands, in a fixed number of queries however many voters and films there are (#154)."""
    suggestions = list(board.candidates())
    ids = [suggestion.pk for suggestion in suggestions]
    voters = [(each.voter_id, each.name, each.scored) for each in progress.of_every_voter()]
    records = list(BallotRecord.objects.filter(suggestion__in=ids).values_list("voter_id", "suggestion_id", "score", "vetoed", "seen_it"))
    vetoed = {(voter_id, suggestion_id) for voter_id, suggestion_id, _, was_vetoed, _ in records if was_vetoed}
    reasons = {
        (author_id, suggestion_id): text
        for suggestion_id, author_id, text in Note.objects.filter(suggestion__in=ids, author__isnull=False).values_list("suggestion_id", "author_id", "text")
        if (author_id, suggestion_id) in vetoed
    }
    return build(voters, [(suggestion.pk, suggestion.film) for suggestion in suggestions], records, reasons, viewer.pk)
