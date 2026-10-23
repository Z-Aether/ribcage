"""Find: TMDB's title search, narrowed by a trailing year, as the picker's results. Pure over a search function (#21, #92)."""

import re
from dataclasses import dataclass

from ribcage.films.tmdb import search_results

# The picker shows this many results, in TMDB's order (#19, #21).
PICKER_SIZE = 5
# The group's year and TMDB's often differ by one, as Mārama's and Insidious's do (#57, #61).
YEAR_MARGIN = 1
TRAILING_YEAR = re.compile(r"^(?P<title>.*\S)\s+\(?(?P<year>\d{4})\)?$")


@dataclass(frozen=True)
class Query:
    title: str
    year: int | None


def parsed(text):
    """The title and its trailing year, if any; a query that is only a year is a title (#92)."""
    text = " ".join(text.split())
    if match := TRAILING_YEAR.match(text):
        return Query(match["title"], int(match["year"]))
    return Query(text, None)


def find(text, search):
    """The picker's results for the typed text. `search` takes a title and answers as TMDB's /search/movie does.

    The ±1 filter runs here, over a title-only search, since TMDB's own year filter misses by one (#61). A trailing number
    can be the title's own, as in Blade Runner 2049, so when narrowing leaves nothing the whole text is searched as a title.
    """
    query = parsed(text)
    if not query.title:
        return ()
    if query.year is not None:
        near = tuple(
            result
            for result in search_results(search(query.title))
            if result.year is not None and abs(result.year - query.year) <= YEAR_MARGIN
        )
        if near:
            return near[:PICKER_SIZE]
    return search_results(search(" ".join(text.split())))[:PICKER_SIZE]
