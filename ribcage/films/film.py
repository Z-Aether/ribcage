from dataclasses import dataclass
from enum import StrEnum


class RuntimeSource(StrEnum):
    TMDB = "tmdb"
    HAND_ENTERED = "hand-entered"


@dataclass(frozen=True)
class Film:
    """A film as the shared components and the models meet it: plain data, no synopsis or genres (#21)."""

    tmdb_id: int | None
    # TMDB's en-US title leads everywhere; a hand-entered film's is shown as typed (#38).
    title: str
    original_title: str | None
    year: int | None
    directors: tuple[str, ...]
    certificate: str | None
    trailer_key: str | None
    runtime: int | None
    runtime_source: RuntimeSource
    # A path on TMDB's keyless image CDN; None means the title card stands in (#5, #38).
    poster_path: str | None
    imdb_id: str | None


def hand_entered(title, year, runtime):
    return Film(
        tmdb_id=None,
        title=title,
        original_title=None,
        year=year,
        directors=(),
        certificate=None,
        trailer_key=None,
        runtime=runtime,
        runtime_source=RuntimeSource.HAND_ENTERED,
        poster_path=None,
        imdb_id=None,
    )
