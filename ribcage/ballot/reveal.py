"""The reveal's matrix: every voter's score on every film of the ballot, plain data for `components/reveal.html` from one loader (#29, #154).

#157 sorts it by a query value, #158 opens a card under a row (`ballot.revealed_card`) and #161 draws it again behind the evening, so the page's view only calls `load`.
"""

from dataclasses import dataclass, replace

from ribcage.ballot import board, progress
from ribcage.ballot.models import BallotRecord
from ribcage.films.card import Chip, RevealBar
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
    # The header's link, `?sort=...`, the ▾ or ▴ the active column wears and its aria-sort value (#157).
    link: str = ""
    marker: str = ""
    aria_sort: str = ""


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
    # The sort in force as its query value, empty for points: what a link that keeps the sort carries (#157, #158).
    sort: str = ""
    # The *Film* header's link, marker and aria-sort value.
    film_link: str = "?sort=film"
    film_marker: str = ""
    film_aria_sort: str = ""
    # *Points* reverses like the others while active (▾ highest first, the default; ▴ lowest first) and otherwise sorts highest first (#157).
    points_link: str = "?sort=-points"
    points_marker: str = "▾"
    points_aria_sort: str = "descending"


def cell_of(name, mine, record, reason):
    score, vetoed, seen_it = record if record else (None, False, False)
    if vetoed:
        return Cell("veto", "☒", seen_it, mine, reason, f"{name} vetoed it" + (f": {reason}" if reason else ""))
    for each, key, sign, words in board.SCALE:
        if score == each:
            return Cell(key, sign, seen_it, mine, "", f"{name}: {words}")
    return Cell("blank", "", seen_it, mine, "", f"{name}: {BLANK_WORDS}")


# A blank counts 0 but isn't a "don't mind", so it sits between 0 and −1; a veto sorts below −1 (#157).
BLANK_RANK = -0.5
VETO_RANK = -2
REVERSED = "-"
FILM = "film"
POINTS = "points"
MARKERS = {False: "▾", True: "▴"}
# A score runs highest first by default, so ▾ is descending; *Film* runs A to Z, so ▾ is ascending.
SCORE_ARIA = {False: "descending", True: "ascending"}
FILM_ARIA = {False: "ascending", True: "descending"}


def rank(record):
    score, vetoed, _ = record if record else (None, False, False)
    if vetoed:
        return VETO_RANK
    return BLANK_RANK if score is None else score


def parse_sort(sort, voter_ids):
    """(what to sort by, reversed) from a query value: `film`, `points`, a voter's id, any with a leading `-`; anything else is points, highest first (#157)."""
    reverse = str(sort).startswith(REVERSED)
    token = str(sort).removeprefix(REVERSED)
    if token == FILM:
        return FILM, reverse
    if token == POINTS:
        return POINTS, reverse
    if token.isascii() and token.isdigit() and int(token) in voter_ids:
        return int(token), reverse
    return None, False


def build(voters, films, records, reasons, viewer_id, sort=""):
    """The matrix from plain data.

    `voters` is (id, name, scored) in the Roster's order, `films` is (suggestion id, Film) for the ballot,
    `records` is (voter id, suggestion id, score, vetoed, seen it) and `reasons` is {(voter id, suggestion id): the note}.
    `sort` is `film`, `points` or a voter's id, any led by `-` to reverse; by default and when unknown it is points, highest first, and films tied on points keep title order A to Z whichever way it runs (#157).
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
    by, reverse = parse_sort(sort, {voter_id for voter_id, _, _ in voters})
    by_points = sorted(standing, key=lambda each: (-each[2], each[1].title.casefold(), each[1].title, each[0]))
    lowest_first = sorted(standing, key=lambda each: (each[2], each[1].title.casefold(), each[1].title, each[0]))
    if by == FILM:
        ordered = sorted(standing, key=lambda each: (each[1].title.casefold(), each[1].title, each[0]), reverse=reverse)
    elif by not in (None, POINTS):
        # Stable over the points order, so ties fall to points then title (#157).
        ordered = sorted(by_points, key=lambda each: rank(held.get((by, each[0]))), reverse=not reverse)
    else:
        ordered = lowest_first if by == POINTS and reverse else by_points
    rows = tuple(
        Row(suggestion_id, film, points, round(100 * abs(points) / longest), points < 0, vetoers, cells)
        for suggestion_id, film, points, vetoers, cells in ordered
    )

    def toward(key):
        return f"?sort={REVERSED if by == key and not reverse else ''}{key}"

    # Points is active in the default order too, where its link reverses it.
    points_on = by in (None, POINTS)
    points_reversed = by == POINTS and reverse
    columns = tuple(
        replace(
            each,
            link=toward(each.voter_id),
            marker=MARKERS[reverse] if by == each.voter_id else "",
            aria_sort=SCORE_ARIA[reverse] if by == each.voter_id else "",
        )
        for each in columns
    )
    token = "" if by is None or (by == POINTS and not reverse) else f"{REVERSED if reverse else ''}{by}"
    by_film = by == FILM
    return Reveal(
        columns,
        rows,
        size,
        sort=token,
        film_link=toward(FILM),
        film_marker=MARKERS[reverse] if by_film else "",
        film_aria_sort=FILM_ARIA[reverse] if by_film else "",
        points_link=f"?sort={'' if points_reversed else REVERSED + POINTS}" if points_on else "?sort=",
        points_marker=MARKERS[points_reversed] if points_on else "",
        points_aria_sort=SCORE_ARIA[points_reversed] if points_on else "",
    )


def chip_words(name, cell):
    """What a chip says to a screen reader: the voter, their score or *vetoed*, and *seen it*, without the veto's reason, which the card's notes carry (#153, #158)."""
    if cell.key == "veto":
        said = "vetoed"
    else:
        said = next((words for _, key, _, words in board.SCALE if key == cell.key), "")
    return ", ".join(part for part in (name, said, "seen it" if cell.seen_it else "") if part)


def bar_of(shown, suggestion_id):
    """The reveal bar for one film of the matrix, from the same cells, points and *didn't vote* the rows and headers carry (#158).

    A voter with a score, a veto or a seen it on the film has a chip; one with a blank and nothing seen has none.
    """
    row = next(each for each in shown.rows if each.suggestion_id == suggestion_id)
    chips = tuple(
        Chip(column.name, cell.key, cell.sign, cell.seen_it, cell.mine, chip_words(column.name, cell))
        for column, cell in zip(shown.columns, row.cells, strict=True)
        if cell.key != "blank" or cell.seen_it
    )
    return RevealBar(chips, row.points, tuple(column.name for column in shown.columns if column.didnt_vote))


def load(viewer, sort=""):
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
    return build(voters, [(suggestion.pk, suggestion.film) for suggestion in suggestions], records, reasons, viewer.pk, sort)
