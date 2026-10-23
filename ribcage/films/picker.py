from dataclasses import dataclass

from ribcage.films.tmdb import SearchResult


@dataclass(frozen=True)
class PickerTile:
    """One result as the picker shows it: a poster tile, marked when the film is already in the pool (#5, #26 §3)."""

    film: SearchResult
    # The kept name of the film's suggester, when it is already in the pool.
    suggested_by: str | None = None
    # The pool's suggestion of it, whose card choosing the tile opens; the gallery's sample has none.
    suggestion_id: int | None = None
    # The searching voter's own film reads by you, not their name (#92; the dev, 2026-10-23).
    yours: bool = False

    @property
    def caption(self):
        if self.yours:
            return "already suggested by you"
        return f"already suggested by {self.suggested_by}" if self.suggested_by else ""


@dataclass(frozen=True)
class Picker:
    """What find shows under its box, as plain data: nothing yet, TMDB's results, none, or the outage (#21, #92)."""

    searched: bool = False
    tiles: tuple[PickerTile, ...] = ()
    # TMDB not answering, which is not the same as no results (#21, #32).
    outage: bool = False
    # Whether choosing a tile leads anywhere; the gallery's sample stands alone, with no step to swap in (#93).
    choosable: bool = True
